---
title: Polly AI
emoji: 🦜
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: AI debate coach - real-time facial, vocal and speech analysis
---

# Polly AI

An AI debate coach. Record a practice argument and Polly analyses your facial
expressions, vocal tone and speech patterns, then returns a scored report.

Grant camera and microphone access when prompted — analysis runs on the live
capture.

**Components that cannot be measured are omitted rather than defaulted**, so a
number in the report always means it was measured. Without a `GEMINI_API_KEY`
secret the camera, face detection, emotion tracking and voice measurement all
work; the transcript and coaching replies report themselves unavailable.

Source: https://github.com/bryan3342/Polly-AI
