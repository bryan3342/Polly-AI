# Deploying Polly AI to Cloud Run (free tier)

The whole app runs as one container. This directory holds the pieces needed to
run it inside Google Cloud Run's **always-free** tier rather than merely cheaply.

## What "free" actually depends on

Cloud Run's free allowance is per billing account per month, for services using
**request-based billing** (the default — do not switch to instance-based):

| Resource | Free per month | What it means here |
|---|---|---|
| CPU | 180,000 vCPU-seconds | **50 hours** of billed instance time at 1 vCPU |
| Memory | 360,000 GiB-seconds | 100 hours at 1 GiB — not the binding limit |
| Requests | 2,000,000 | Not reachable for this app |
| Egress | 1 GiB from North America | ~15,000 SPA loads — this service serves the SPA |

Two things are billed separately and can produce a charge even when Cloud Run
itself is free:

- **Artifact Registry** — 0.5 GiB stored free, then ~$0.10/GiB/month. This one
  does cost a few cents a month; see below.
- **Cloud Build** — 2,500 build-minutes/month free (avoided entirely if you
  build in GitHub Actions, as the workflow in this repo does).

### CPU is the constraint, and WebSockets are why

Billed instance time covers container startup, shutdown, and **any period with
at least one request in flight**. A WebSocket is a single long-lived request, so
a connected browser tab bills continuously — whether or not anyone is using it.

Three behaviours in the app keep that honest, and the free tier depends on all
three working together:

| Tab state | Client sends | Result |
|---|---|---|
| Visible, recording | frames at 1/s | billed, and earning it |
| Visible, idle or camera off | frames at 1/5s, or a keepalive every 45s | stays connected — the user is there |
| **Hidden** | **nothing at all** | reaped after 120s, instance scales to zero |

The hidden-tab case is the one that matters, and the client's `document.hidden`
guard is load-bearing: browsers keep hidden-tab timers running, just throttled to
roughly once a minute, and one frame a minute would keep a connection looking
busy forever.

The keepalive is what makes a window this short safe. Reconnecting starts a
**new** session — the server mints session ids and never accepts one from the
client — so a reaped session loses its topic and coaching history. Without the
keepalive, a user reading their report with the camera off would be silent, and
would lose it. Set `WS_IDLE_TIMEOUT_SECONDS=0` to disable reaping entirely on an
always-on host.

## One-time setup

```bash
PROJECT_ID=your-project
REGION=us-central1

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
    secretmanager.googleapis.com

gcloud artifacts repositories create polly \
    --repository-format=docker --location="$REGION"
```

### Artifact Registry is where "free" actually leaks

This is the one line item that is *not* free, and no amount of image slimming in
this repo has got it to zero. Measured for the x86_64 image:

| | Registry footprint | Monthly cost |
|---|---|---|
| Before the dependency work | ~1.13 GiB | ~$0.06 |
| Now (`tensorflow-cpu`, headless OpenCV) | ~840 MiB | **~$0.03** |
| Free allowance | 0.5 GiB | $0.00 |

Getting under 0.5 GiB means removing the two largest remaining items — apt
`ffmpeg` (409 MB installed) and the librosa stack (numba, llvmlite,
scikit-learn, ~250 MB) — which would mean re-implementing audio decoding on
PyAV and pitch tracking on NumPy. That trades measurement fidelity for about
three cents a month, so it has not been done.

Repeated deploys are cheaper than they look: image layers are content-addressed
and shared, so a deploy that only changes application code adds a few MB rather
than another 840. The dependency layer is re-pushed in full whenever
`requirements.txt` changes. Set the cleanup policy anyway — without it those old
dependency layers accumulate for good.

```bash
gcloud artifacts repositories set-cleanup-policies polly \
    --location="$REGION" --policy=deploy/cloudrun/cleanup-policy.json
```

Check what it would remove before trusting it:

```bash
gcloud artifacts repositories set-cleanup-policies polly \
    --location="$REGION" --policy=deploy/cloudrun/cleanup-policy.json --dry-run
```

### The API key

Optional. Without it the camera, face detection, emotion tracking and voice
measurement all still work; the transcript and coaching replies report
themselves unavailable.

```bash
printf 'your-key' | gcloud secrets create gemini-api-key --data-file=-
gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:$(gcloud projects describe "$PROJECT_ID" \
        --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
    --role=roles/secretmanager.secretAccessor
```

## Deploy

```bash
gcloud auth configure-docker "$REGION-docker.pkg.dev"
docker build --platform linux/amd64 -t "$REGION-docker.pkg.dev/$PROJECT_ID/polly/polly-ai:latest" .
docker push "$REGION-docker.pkg.dev/$PROJECT_ID/polly/polly-ai:latest"

sed "s/PROJECT_ID/$PROJECT_ID/g" deploy/cloudrun/service.yaml \
  | gcloud run services replace - --region="$REGION"

gcloud run services add-iam-policy-binding polly-ai --region="$REGION" \
    --member=allUsers --role=roles/run.invoker
```

`--platform linux/amd64` matters on an Apple Silicon machine: Cloud Run is
x86_64, and `tensorflow-cpu` publishes x86_64 wheels only.

## The frontend is served from here

One container, one origin, one URL — the SPA, the API and the WebSocket all come
from this service, and the browser never makes a cross-origin request.

That spends the 1 GiB monthly egress allowance on static assets, at ~72 KB
gzipped per load: roughly **15,000 page loads a month** before egress bills. That
is a long way from being the binding limit, and single-origin keeps the whole
deployment one thing to reason about.

If the app ever outgrows that, the split is already supported — the client reads
`VITE_WS_URL` — and moving the SPA to Cloudflare Pages takes Cloud Run's egress
to approximately zero:

```bash
cd frontend
VITE_WS_URL=wss://polly-ai-xxxxx-uc.a.run.app npm run build
npx wrangler pages deploy dist
```

That also means setting `CORS_ORIGINS` in `service.yaml` to the Pages origin.

## Guard rails

Cloud Run does **not** stop at the free tier; it bills past it. `maxScale: 3`
bounds the damage from a spike or a client stuck reconnecting. Add an alert too:

```bash
gcloud billing budgets create --billing-account=YOUR_BILLING_ACCOUNT \
    --display-name="polly-ai" --budget-amount=1USD \
    --threshold-rule=percent=0.5 --threshold-rule=percent=1.0
```

Watch actual consumption on the `container/billable_instance_time` metric.
