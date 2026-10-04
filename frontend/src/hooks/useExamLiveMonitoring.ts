import { useEffect, useRef, useState, useCallback } from 'react';
import {
  CandidateSessionRow,
  LiveMonitorMessage,
  LiveViolationEvent,
  LiveSessionUpdate,
} from '../types';

interface UseExamLiveMonitoringOptions {
  examId: string | undefined;
  token: string | null;
  enabled?: boolean;
  onViolationReceived?: (event: LiveViolationEvent) => void;
}

interface UseExamLiveMonitoringResult {
  isConnected: boolean;
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error';
  recentViolations: LiveViolationEvent[];
  liveSessions: Record<string, CandidateSessionRow>;
  setInitialSessions: (sessions: CandidateSessionRow[]) => void;
  updateSessionLocally: (sessionId: string, partial: Partial<CandidateSessionRow>) => void;
  reconnect: () => void;
}

export function useExamLiveMonitoring({
  examId,
  token,
  enabled = true,
  onViolationReceived,
}: UseExamLiveMonitoringOptions): UseExamLiveMonitoringResult {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<
    'connecting' | 'connected' | 'disconnected' | 'error'
  >('disconnected');
  const [recentViolations, setRecentViolations] = useState<LiveViolationEvent[]>([]);
  const [liveSessions, setLiveSessions] = useState<Record<string, CandidateSessionRow>>({});

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const pingIntervalRef = useRef<number | null>(null);

  const setInitialSessions = useCallback((sessions: CandidateSessionRow[]) => {
    const map: Record<string, CandidateSessionRow> = {};
    for (const s of sessions) {
      map[s.session_id] = s;
    }
    setLiveSessions((prev) => ({
      ...map,
      ...prev, // Keep any live WebSocket updates that already arrived
    }));
  }, []);

  const updateSessionLocally = useCallback((sessionId: string, partial: Partial<CandidateSessionRow>) => {
    setLiveSessions((prev) => {
      const existing = prev[sessionId];
      if (!existing) return prev;
      return {
        ...prev,
        [sessionId]: {
          ...existing,
          ...partial,
        },
      };
    });
  }, []);

  const connect = useCallback(() => {
    if (!examId || !token || !enabled) return;

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnectionStatus('connecting');

    // Build WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Use window.location.host for Vite proxy, or fallback directly to port 8000
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/v1/admin/ws/exams/${examId}?token=${encodeURIComponent(token)}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setConnectionStatus('connected');
        reconnectAttempts.current = 0;

        // Keepalive heartbeat
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 20000);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as LiveMonitorMessage;

          if (msg.type === 'initial_state') {
            if (msg.sessions && Array.isArray(msg.sessions)) {
              setInitialSessions(msg.sessions);
            }
          } else if (msg.type === 'violation_event') {
            const vEvent = msg as LiveViolationEvent;
            setRecentViolations((prev) => [vEvent, ...prev].slice(0, 50));

            // Update candidate session in live state
            setLiveSessions((prev) => {
              const current = prev[vEvent.session_id];
              if (!current) return prev;

              const newViolCount = (current.violation_count || 0) + 1;
              const evidenceUrl = vEvent.violation.evidence_url || current.latest_snapshot_url;

              return {
                ...prev,
                [vEvent.session_id]: {
                  ...current,
                  trust_score: vEvent.trust_score,
                  violation_count: newViolCount,
                  latest_snapshot_url: evidenceUrl,
                },
              };
            });

            if (onViolationReceived) {
              onViolationReceived(vEvent);
            }
          } else if (msg.type === 'session_update') {
            const sUpdate = msg as LiveSessionUpdate;
            setLiveSessions((prev) => {
              const current = prev[sUpdate.session_id];
              if (!current) return prev;

              const summary = sUpdate.session_summary || {};
              return {
                ...prev,
                [sUpdate.session_id]: {
                  ...current,
                  ...summary,
                  trust_score: summary.trust_score !== undefined ? summary.trust_score : current.trust_score,
                  review_status: (summary.review_status as CandidateSessionRow['review_status']) ?? current.review_status,
                },
              };
            });
          }
        } catch (err) {
          console.error('[AdminWS] Failed to parse message', err);
        }
      };

      ws.onerror = (err) => {
        console.warn('[AdminWS] WebSocket error encountered', err);
        setConnectionStatus('error');
      };

      ws.onclose = () => {
        setIsConnected(false);
        setConnectionStatus('disconnected');
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Attempt reconnection with backoff if component is still active
        if (enabled && reconnectAttempts.current < 8) {
          const delay = Math.min(1000 * Math.pow(1.5, reconnectAttempts.current), 15000);
          reconnectAttempts.current += 1;
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect();
          }, delay);
        }
      };
    } catch (err) {
      console.error('[AdminWS] Connection attempt threw error', err);
      setConnectionStatus('error');
    }
  }, [examId, token, enabled, onViolationReceived, setInitialSessions]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const reconnect = useCallback(() => {
    reconnectAttempts.current = 0;
    connect();
  }, [connect]);

  return {
    isConnected,
    connectionStatus,
    recentViolations,
    liveSessions,
    setInitialSessions,
    updateSessionLocally,
    reconnect,
  };
}
