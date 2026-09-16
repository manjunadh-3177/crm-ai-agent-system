import { useEffect, useState } from "react";

import type { Deal, Stage } from "../lib/api";
import { normalizeStageName, safeNumber, formatCurrency, formatDate } from "../lib/formatters";
import { PIPELINE_STAGE_ORDER, PIPELINE_STAGE_KEYS } from "../types/appState";

export function PipelinePage({
  deals,
  stages,
  loading,
  onMoveDealStage,
  onOpenDeal,
  onCreateDealClick,
}: {
  deals: Deal[];
  stages: Stage[];
  loading: boolean;
  onMoveDealStage: (dealId: string, stageId: string) => Promise<void>;
  onOpenDeal: (dealId: string) => void;
  onCreateDealClick: () => void;
}) {
  const [boardDeals, setBoardDeals] = useState<Deal[]>(deals);
  const [draggedDealId, setDraggedDealId] = useState<string | null>(null);
  const [dropStageId, setDropStageId] = useState<string | null>(null);
  const [movingDealId, setMovingDealId] = useState<string | null>(null);

  useEffect(() => {
    setBoardDeals(deals);
  }, [deals]);

  const stageByKey = new Map<string, Stage>();
  for (const stage of stages) {
    const key = normalizeStageName(stage.name);
    if (!PIPELINE_STAGE_KEYS.has(key) || stageByKey.has(key)) {
      continue;
    }
    stageByKey.set(key, stage);
  }
  const orderedStages = PIPELINE_STAGE_ORDER.map((stageName) => stageByKey.get(normalizeStageName(stageName))).filter(
    (stage): stage is Stage => Boolean(stage),
  );
  const openDeals = boardDeals.filter((deal) => !deal.stage.is_closed);
  const wonDeals = boardDeals.filter((deal) => normalizeStageName(deal.stage.name) === "won");
  const lostDeals = boardDeals.filter((deal) => normalizeStageName(deal.stage.name) === "lost");
  const totalPipeline = openDeals.reduce((sum, deal) => sum + safeNumber(deal.amount), 0);
  const weightedPipeline = openDeals.reduce(
    (sum, deal) => sum + safeNumber(deal.amount) * (safeNumber(deal.probability) / 100),
    0,
  );
  const closedDeals = wonDeals.length + lostDeals.length;
  const conversionRate = closedDeals > 0 ? Math.round((wonDeals.length / closedDeals) * 100) : 0;
  const totalOpenDealCount = openDeals.length;
  const currentMonth = new Date().getMonth();
  const currentYear = new Date().getFullYear();
  const wonThisMonth = boardDeals.reduce((sum, deal) => {
    const updatedAt = new Date(deal.updated_at);
    const isWonStage = normalizeStageName(deal.stage.name) === "won";
    const isCurrentMonth =
      updatedAt.getMonth() === currentMonth && updatedAt.getFullYear() === currentYear;
    return isWonStage && isCurrentMonth ? sum + safeNumber(deal.amount) : sum;
  }, 0);
  const hasPipelineShape = orderedStages.length > 0;
  const hasDeals = boardDeals.length > 0;

  async function handleDrop(stageId: string) {
    if (!draggedDealId) {
      return;
    }

    const previousDeals = boardDeals;
    const draggedDeal = previousDeals.find((deal) => deal.id === draggedDealId);
    if (!draggedDeal || draggedDeal.stage_id === stageId) {
      setDraggedDealId(null);
      setDropStageId(null);
      return;
    }

    const targetStage = orderedStages.find((stage) => stage.id === stageId);
    if (!targetStage) {
      setDraggedDealId(null);
      setDropStageId(null);
      return;
    }

    setMovingDealId(draggedDealId);
    setBoardDeals((current) =>
      current.map((deal) =>
        deal.id === draggedDealId
          ? {
            ...deal,
            stage_id: targetStage.id,
            stage: targetStage,
          }
          : deal,
      ),
    );

    try {
      await onMoveDealStage(draggedDealId, stageId);
    } catch {
      setBoardDeals(previousDeals);
    } finally {
      setDraggedDealId(null);
      setDropStageId(null);
      setMovingDealId(null);
    }
  }

  return (
    <section className="stack">
      <div className="card-grid">
        <article className="summary-card">
          <p>📈 Total Pipeline</p>
          <strong>{formatCurrency(totalPipeline, "USD")}</strong>
        </article>
        <article className="summary-card">
          <p>🔮 Weighted Pipeline</p>
          <strong>{formatCurrency(weightedPipeline, "USD")}</strong>
        </article>
        <article className="summary-card">
          <p>💰 Won This Month</p>
          <strong>{formatCurrency(wonThisMonth, "USD")}</strong>
        </article>
        <article className="summary-card">
          <p>Open Deals</p>
          <strong>{totalOpenDealCount}</strong>
        </article>
        <article className="summary-card">
          <p>Win Rate</p>
          <strong>{conversionRate}%</strong>
        </article>
      </div>

      <div className="panel-card pipeline-conversion">
        <strong>Conversion summary</strong>
        <span>
          {wonDeals.length} won / {lostDeals.length} lost from {closedDeals} closed deals.
          {" "}Weighted open pipeline is {formatCurrency(weightedPipeline, "USD")}.
        </span>
      </div>

      {!loading && (!hasPipelineShape || !hasDeals) ? (
        <div className="panel-card pipeline-empty-state">
          <div>
            <h3>No deals yet</h3>
            <p className="modal-copy">Create your first deal to start tracking sales value by stage.</p>
          </div>
          <button className="primary-button" onClick={onCreateDealClick} type="button">
            Create your first deal
          </button>
        </div>
      ) : null}

      {hasPipelineShape ? <div className="pipeline-grid">
        {orderedStages.map((stage) => {
          const stageKey = normalizeStageName(stage.name);
          const stageDeals = boardDeals.filter((deal) => normalizeStageName(deal.stage.name) === stageKey);
          const stageTotal = stageDeals.reduce((sum, deal) => sum + safeNumber(deal.amount), 0);

          return (
            <article
              key={stage.id}
              className={`pipeline-column ${dropStageId === stage.id ? "drag-target" : ""}`}
              onDragOver={(event) => {
                event.preventDefault();
                if (draggedDealId) {
                  setDropStageId(stage.id);
                }
              }}
              onDragLeave={() => {
                if (dropStageId === stage.id) {
                  setDropStageId(null);
                }
              }}
              onDrop={(event) => {
                event.preventDefault();
                void handleDrop(stage.id);
              }}
            >
              <header className="pipeline-header">
                <div className="pipeline-header-stack">
                  <h3>{stage.name}</h3>
                  <small>{loading ? "Loading..." : formatCurrency(stageTotal, "USD")}</small>
                </div>
                <span>{loading ? "..." : stageDeals.length}</span>
              </header>

              <div className="pipeline-list">
                {loading ? (
                  <div className="pipeline-card muted">Loading...</div>
                ) : stageDeals.length === 0 ? (
                  <div className="pipeline-card muted empty-drop-zone">Drop deals here</div>
                ) : (
                  stageDeals.map((deal) => (
                    <button
                      key={deal.id}
                      className={`pipeline-card pipeline-card-button ${movingDealId === deal.id ? "dragging" : ""}`}
                      draggable
                      onClick={() => onOpenDeal(deal.id)}
                      onDragStart={() => {
                        setDraggedDealId(deal.id);
                        setDropStageId(stage.id);
                      }}
                      onDragEnd={() => {
                        setDraggedDealId(null);
                        setDropStageId(null);
                      }}
                      type="button"
                    >
                      <strong>{deal.name}</strong>
                      <span>{formatCurrency(safeNumber(deal.amount), deal.currency)}</span>
                      <small>{deal.account?.name ?? deal.contact?.email ?? "Direct deal"}</small>
                      <small>{safeNumber(deal.probability)}% probability</small>
                      <small>
                        {deal.expected_close_date ? `Close ${formatDate(deal.expected_close_date)}` : "No close date"}
                      </small>
                    </button>
                  ))
                )}
              </div>
            </article>
          );
        })}
      </div> : null}
    </section>
  );
}
