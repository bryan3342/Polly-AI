/**
 * Minimal Markdown renderer for coach messages.
 *
 * The coaching model replies in Markdown — "**Record**", "### Strengths",
 * bullet lists — and the UI rendered it as literal text, so users read
 * asterisks and hashes instead of emphasis and structure.
 *
 * This returns React elements rather than an HTML string, so model output is
 * escaped by React and can never inject markup. That safety property is the
 * reason not to reach for `dangerouslySetInnerHTML` with a regex, and the
 * reason a full Markdown library (remark and its dependency tree) is more than
 * this needs: the grammar below covers what the model actually emits, in a file
 * small enough to audit.
 *
 * Anything unrecognised falls through as plain text — never as markup.
 */

/* Inline: **bold**, *italic*, `code`. Split on all three at once so the parts
   stay in order and nesting cannot produce interleaved tags.
 *
 * A marker must be followed immediately by a non-space, so "2 * 3 * 4 = 24"
 * stays arithmetic instead of italicising " 3 ". */
const INLINE = /(\*\*(?![\s*])(?:[^*]*[^\s*])?\*\*|\*(?![\s*])(?:[^*\n]*[^\s*])?\*|`[^`\n]+`)/g;

function renderInline(text, keyPrefix) {
    return text.split(INLINE).filter(Boolean).map((part, i) => {
        const key = `${keyPrefix}-${i}`;
        if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
            return <strong key={key}>{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
            return <code key={key}>{part.slice(1, -1)}</code>;
        }
        if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
            return <em key={key}>{part.slice(1, -1)}</em>;
        }
        return part;
    });
}

const HEADING = /^(#{1,6})\s+(.*)$/;
const BULLET = /^\s*[-*+]\s+(.*)$/;
const NUMBERED = /^\s*(\d+)[.)]\s+(.*)$/;

/* Group consecutive lines into blocks: a run of bullets becomes one <ul> rather
   than a stack of single-item lists, and consecutive prose lines become one
   paragraph. Both accumulators are held open and closed explicitly, so a blank
   line ends whatever is open. */
function groupBlocks(lines) {
    const blocks = [];
    let list = null;
    let paragraph = null;

    const closeList = () => { if (list) { blocks.push(list); list = null; } };
    const closeParagraph = () => { if (paragraph) { blocks.push(paragraph); paragraph = null; } };
    const closeAll = () => { closeList(); closeParagraph(); };

    for (const line of lines) {
        const bullet = line.match(BULLET);
        const numbered = line.match(NUMBERED);
        const heading = line.match(HEADING);

        if (bullet) {
            closeParagraph();
            if (list?.type !== 'ul') { closeList(); list = { type: 'ul', items: [] }; }
            list.items.push(bullet[1]);
        } else if (numbered) {
            closeParagraph();
            if (list?.type !== 'ol') { closeList(); list = { type: 'ol', items: [] }; }
            list.items.push(numbered[2]);
        } else if (heading) {
            closeAll();
            blocks.push({ type: 'heading', level: heading[1].length, text: heading[2] });
        } else if (line.trim() === '') {
            closeAll();
        } else {
            closeList();
            // Wrapped lines belong to the same paragraph; a blank line ends it.
            if (paragraph) paragraph.text += `\n${line}`;
            else paragraph = { type: 'paragraph', text: line };
        }
    }
    closeAll();
    return blocks;
}

export default function Markdown({ children }) {
    if (typeof children !== 'string' || !children.trim()) return null;

    const blocks = groupBlocks(children.split('\n'));

    return (
        <div className="markdown">
            {blocks.map((block, i) => {
                if (block.type === 'heading') {
                    // Coach replies sit inside a chat bubble, so headings render as
                    // a styled strong line rather than h1-h6 competing with page
                    // structure for assistive technology.
                    return (
                        <div key={i} className={`md-heading md-h${block.level}`}>
                            {renderInline(block.text, i)}
                        </div>
                    );
                }
                if (block.type === 'ul' || block.type === 'ol') {
                    const List = block.type;
                    return (
                        <List key={i} className="md-list">
                            {block.items.map((item, j) => (
                                <li key={j}>{renderInline(item, `${i}-${j}`)}</li>
                            ))}
                        </List>
                    );
                }
                return <p key={i} className="md-p">{renderInline(block.text, i)}</p>;
            })}
        </div>
    );
}
