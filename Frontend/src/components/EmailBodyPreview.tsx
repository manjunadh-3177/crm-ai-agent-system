import { splitUnsubscribeFooter } from "../lib/formatters";

export function EmailBodyPreview({ body }: { body: string }) {
  const preview = splitUnsubscribeFooter(body);
  return (
    <div className="email-preview-body">
      <pre className="draft-body">{preview.body}</pre>
      {preview.unsubscribeUrl ? (
        <div className="unsubscribe-preview">
          <span>To stop emails, click</span>
          <a href={preview.unsubscribeUrl} target="_blank" rel="noreferrer">
            Unsubscribe
          </a>
        </div>
      ) : null}
    </div>
  );
}
