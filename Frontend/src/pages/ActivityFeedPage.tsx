import { useState } from "react";

import type { PageProps } from "../types/appState";
import {
  isBusinessActivity,
  formatActionLabel,
  getRelativeTime,
  getActivityIcon,
  getActivityColor,
  formatActivityDescription,
} from "../lib/formatters";

export function ActivityFeedPage({ data, loading }: PageProps) {
  const [showSystemEvents, setShowSystemEvents] = useState(false);

  if (loading && data.activityFeed.length === 0) {
    return (
      <div className="loading-container">
        <p>Loading activity feed...</p>
      </div>
    );
  }

  const filteredFeed = data.activityFeed.filter(item => {
    if (showSystemEvents) return true;
    return isBusinessActivity(item);
  });

  return (
    <section className="page-container animate-fade-in">
      <header className="page-header">
        <div className="header-content">
          <h1 className="page-title">⚡ Activity Feed</h1>
          <p className="page-subtitle">Unified timeline of all CRM updates and notes.</p>
        </div>
        <div className="header-actions">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={showSystemEvents}
              onChange={(e) => setShowSystemEvents(e.target.checked)}
            />
            Show System Events
          </label>
        </div>
      </header>

      {filteredFeed.length === 0 ? (
        <div className="empty-state">
          <p>No recent activity.</p>
        </div>
      ) : (
        <div className="timeline-container page-timeline">
          {filteredFeed.map((item) => (
            <div key={item.id} className="timeline-card" style={{ borderLeftColor: getActivityColor(item.title) }}>
              <div className="timeline-icon-bubble" style={{ background: getActivityColor(item.title) + "15", color: getActivityColor(item.title) }}>
                {getActivityIcon(item.title)}
              </div>
              <div className="timeline-details">
                <div className="timeline-row">
                  <strong className="timeline-label">{formatActionLabel(item.title)}</strong>
                  <span className="timeline-relative">{getRelativeTime(item.time)}</span>
                </div>
                <p className="timeline-msg">{formatActivityDescription(item)}</p>
                {item.entity_type && (
                  <div className="timeline-meta">
                    <span className="meta-tag">
                      {item.entity_type}: {item.entity_id?.substring(0, 8)}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
