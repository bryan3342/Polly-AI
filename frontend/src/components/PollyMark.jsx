/**
 * The Polly parrot mark.
 *
 * Inline SVG rather than an <img>: it inherits sizing from CSS, stays crisp at
 * every density, and costs no extra request.
 *
 * This is the same artwork as public/polly-mark.svg, which serves the favicon
 * and the README. There are two copies because one has to be a file the browser
 * can request and the other has to be a component -- change one, change the
 * other. There are no gradient ids to namespace any more; the mark is flat, so
 * several can render on a page without colliding.
 */
export default function PollyMark({ size = 24, className = '', title = 'Polly AI' }) {
    return (
        <svg
            className={className}
            width={size}
            height={size}
            viewBox="0 0 200 200"
            role="img"
            aria-label={title}
            xmlns="http://www.w3.org/2000/svg"
        >
          <g fill="none" fillRule="evenodd">
            <path d="M28 174 C70 168 122 158 178 149" stroke="#7A8290" strokeWidth="5.5" strokeLinecap="round"/>
            <path d="M110 163 L134 153" stroke="#7A8290" strokeWidth="4" strokeLinecap="round"/>

            {/* tail */}
            <path d="M116 130 C130 150 140 172 137 191 C126 177 114 154 106 136 Z" fill="#D97236"/>
            <path d="M128 124 C146 144 160 167 160 189 C144 173 128 150 118 130 Z" fill="#E07A3E"/>
            <path d="M139 116 C159 132 174 153 178 173 C160 161 143 141 131 124 Z" fill="#D97236"/>

            {/* legs */}
            <path d="M89 138 L89 160" stroke="#7A8290" strokeWidth="7" strokeLinecap="round"/>
            <path d="M104 138 L104 157" stroke="#7A8290" strokeWidth="7" strokeLinecap="round"/>
            <path d="M82 162 L95 158 M99 159 L112 154" stroke="#7A8290" strokeWidth="5" strokeLinecap="round"/>

            {/* body */}
            <ellipse cx="101" cy="102" rx="43" ry="50" fill="#E07A3E"/>

            {/* belly patch, low and forward */}
            <ellipse cx="82" cy="122" rx="20" ry="26" fill="#EFCB92"/>

            {/* wing */}
            <path d="M110 64 C138 70 150 96 147 120 C144 142 128 152 112 147
                     C98 142 95 118 97 98 C99 78 103 64 110 64 Z" fill="#E07A3E"/>
            <path d="M114 78 C133 85 142 102 141 121 M108 94 C125 101 133 116 132 131"
                  stroke="#C96A33" strokeWidth="2.4" strokeLinecap="round" opacity=".42"/>

            {/* head: smaller relative to the body, crown left orange */}
            <circle cx="90" cy="60" r="32" fill="#E07A3E"/>

            {/* white face patch: a tighter mask around the eye, reaching the beak */}
            <path d="M78 30 C60 34 52 48 52 64 C52 80 62 90 78 90
                     C92 90 100 78 100 62 C100 44 90 30 78 30 Z" fill="#FFFFFF"/>

            {/* beak */}
            <path d="M60 38 C38 40 26 52 26 66 C26 80 40 88 58 86
                     C46 76 44 52 60 38 Z" fill="#333B4A"/>
            <path d="M46 72 C36 76 33 83 37 88 C46 93 58 90 62 82 Z" fill="#7A8290"/>

            {/* eye, centred in the white */}
            <circle cx="79" cy="60" r="14" fill="#20293A"/>
            <circle cx="84" cy="54" r="4.6" fill="#FFFFFF"/>
          </g>
        </svg>
    );
}
