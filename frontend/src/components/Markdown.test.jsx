import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import Markdown from './Markdown';

/**
 * The coach replies in Markdown. The UI used to print it literally, so users
 * read "**Record**" and "### Strengths" instead of emphasis and structure.
 */
describe('Markdown', () => {
    it('renders bold instead of printing asterisks', () => {
        const { container } = render(<Markdown>{'Click **Record** to begin.'}</Markdown>);

        expect(container.querySelector('strong')).toHaveTextContent('Record');
        expect(container.textContent).not.toContain('**');
    });

    it('renders italics and inline code', () => {
        const { container } = render(<Markdown>{'Use *pace* and `wpm`.'}</Markdown>);

        expect(container.querySelector('em')).toHaveTextContent('pace');
        expect(container.querySelector('code')).toHaveTextContent('wpm');
        expect(container.textContent).not.toContain('`');
    });

    it('groups consecutive bullets into a single list', () => {
        const { container } = render(
            <Markdown>{'- Slow down\n- Cut fillers\n- Land the claim'}</Markdown>,
        );

        expect(container.querySelectorAll('ul')).toHaveLength(1);
        expect(container.querySelectorAll('li')).toHaveLength(3);
    });

    it('renders numbered lists as an ordered list', () => {
        const { container } = render(<Markdown>{'1. First\n2. Second'}</Markdown>);

        expect(container.querySelectorAll('ol')).toHaveLength(1);
        expect(container.querySelectorAll('li')).toHaveLength(2);
    });

    it('separates a bullet list from a following numbered list', () => {
        const { container } = render(<Markdown>{'- a\n- b\n1. one\n2. two'}</Markdown>);

        expect(container.querySelectorAll('ul')).toHaveLength(1);
        expect(container.querySelectorAll('ol')).toHaveLength(1);
    });

    it('renders headings without the hashes', () => {
        const { container } = render(<Markdown>{'### Strengths\nGood pacing.'}</Markdown>);

        const heading = container.querySelector('.md-heading');
        expect(heading).toHaveTextContent('Strengths');
        expect(container.textContent).not.toContain('#');
    });

    it('keeps blank-line separated paragraphs apart', () => {
        const { container } = render(<Markdown>{'First point.\n\nSecond point.'}</Markdown>);

        expect(container.querySelectorAll('p')).toHaveLength(2);
    });

    it('joins wrapped lines into one paragraph', () => {
        const { container } = render(<Markdown>{'A sentence that\nwraps.'}</Markdown>);

        expect(container.querySelectorAll('p')).toHaveLength(1);
    });

    it('applies emphasis inside list items', () => {
        const { container } = render(<Markdown>{'- Cut **um** and **uh**'}</Markdown>);

        expect(container.querySelectorAll('li strong')).toHaveLength(2);
    });

    it('renders the real welcome message legibly', () => {
        render(
            <Markdown>
                {'Welcome to Polly AI!\n\n1. I\'ve assigned you a topic.\n2. Click **Record** when ready.'}
            </Markdown>,
        );

        expect(screen.getByText('Record').tagName).toBe('STRONG');
        expect(document.body.textContent).not.toMatch(/\*\*/);
    });

    describe('safety', () => {
        it('never turns model output into markup', () => {
            const { container } = render(
                <Markdown>{'<img src=x onerror="alert(1)"> and <script>alert(2)</script>'}</Markdown>,
            );

            expect(container.querySelector('img')).toBeNull();
            expect(container.querySelector('script')).toBeNull();
            // Escaped and shown as text, which is what the user should see.
            expect(container.textContent).toContain('<script>');
        });

        it('leaves unmatched markers as literal text rather than guessing', () => {
            const { container } = render(<Markdown>{'2 * 3 * 4 = 24'}</Markdown>);

            expect(container.querySelector('em')).toBeNull();
            expect(container.textContent).toContain('2 * 3 * 4 = 24');
        });
    });

    describe('edge cases', () => {
        it('renders nothing for empty or whitespace input', () => {
            const { container } = render(<Markdown>{'   '}</Markdown>);
            expect(container.firstChild).toBeNull();
        });

        it('renders nothing for a non-string child', () => {
            const { container } = render(<Markdown>{null}</Markdown>);
            expect(container.firstChild).toBeNull();
        });
    });
});
