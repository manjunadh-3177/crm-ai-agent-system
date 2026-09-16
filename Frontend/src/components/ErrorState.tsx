export function ErrorState({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  return (
    <section className="panel-card error-card">
      <div className="error-header">
        <h3>Unable to complete request</h3>
        <button className="text-button" onClick={onDismiss} type="button">
          Dismiss
        </button>
      </div>
      <p>{message}</p>
    </section>
  );
}
