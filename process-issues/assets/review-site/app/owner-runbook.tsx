"use client";

import { useEffect, useState } from "react";
import { MAX_RUNBOOK_BYTES, parseRunbook } from "../lib/review-runbook.mjs";

type Block = { label: string; kind: "prompt" | "script"; text: string };
type Step = {
  title: string;
  instructions: string;
  links?: { label: string; url: string }[];
  blocks?: Block[];
  pass?: string;
  fail?: string;
  unverified?: string;
};
type Content = { steps: Step[] } | { legacy: string };

function CopyBlock({ block }: { block: Block }) {
  const [status, setStatus] = useState("");
  const label = block.kind === "script" ? "Copy script" : "Copy prompt";

  async function copy() {
    try {
      await navigator.clipboard.writeText(block.text);
      setStatus("Copied.");
    } catch {
      setStatus("Clipboard unavailable. Select and copy the text below.");
    }
  }

  return (
    <div className="runbook-block">
      <div className="runbook-block-heading">
        <h4>{block.label}</h4>
        <button type="button" onClick={copy} aria-label={label + ": " + block.label}>{label}</button>
      </div>
      <p className="runbook-copy-status" role="status">{status}</p>
      <pre><code>{block.text}</code></pre>
    </div>
  );
}

export default function OwnerRunbook({ src, mime }: { src: string; mime: string }) {
  const [content, setContent] = useState<Content | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      const response = await fetch(src, { signal: controller.signal });
      if (!response.ok || Number(response.headers.get("Content-Length")) > MAX_RUNBOOK_BYTES) {
        throw Error("Runbook unavailable");
      }
      const bytes = await response.arrayBuffer();
      if (bytes.byteLength > MAX_RUNBOOK_BYTES) throw Error("Runbook too large");
      return mime === "application/json"
        ? parseRunbook(bytes) as Content
        : { legacy: new TextDecoder("utf-8", { fatal: true }).decode(bytes) };
    }
    load().then(value => {
      if (!controller.signal.aborted) setContent(value);
    }).catch(() => {
      if (!controller.signal.aborted) setFailed(true);
    });
    return () => controller.abort();
  }, [src, mime]);

  return (
    <section id="owner-verification" className="runbook" aria-labelledby="runbook-title">
      <h2 id="runbook-title">Owner verification</h2>
      {failed && <p className="notice" role="alert">The runbook could not be displayed. <a href={src} download>Download the original runbook</a>.</p>}
      {!failed && !content && <p role="status">Loading verification steps…</p>}
      {content && "legacy" in content && <p className="runbook-instructions">{content.legacy}</p>}
      {content && "steps" in content && (
        <ol className="runbook-steps">
          {content.steps.map((step, index) => (
            <li key={index}>
              <h3>{step.title}</h3>
              <p className="runbook-instructions">{step.instructions}</p>
              {step.links?.length ? (
                <ul className="runbook-links">
                  {step.links.map((link, linkIndex) => (
                    <li key={linkIndex}><a href={link.url} target="_blank" rel="noreferrer">{link.label}</a></li>
                  ))}
                </ul>
              ) : null}
              {step.blocks?.map((block, blockIndex) => <CopyBlock key={blockIndex} block={block} />)}
              {(step.pass || step.fail || step.unverified) && (
                <dl className="runbook-results">
                  {step.pass && <div><dt>Pass</dt><dd>{step.pass}</dd></div>}
                  {step.fail && <div><dt>Fail</dt><dd>{step.fail}</dd></div>}
                  {step.unverified && <div><dt>Unverified</dt><dd>{step.unverified}</dd></div>}
                </dl>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
