/**
 * Real-time WebSocket Layer — WebSocket Server
 */

import { FastifyInstance } from 'fastify';
import { WebSocket, WebSocketServer } from 'ws';
import { realtimeHub } from './realtime.hub.js';
import { SubscriptionFilter, ClientConnection, RealtimeEvent } from './realtime.types.js';
import { ChannelName, resolveChannelFilter, ALL_CHANNELS, CHANNEL_EVENT_MAP } from './realtime.channels.js';

let wss: WebSocketServer | null = null;

// ═══════════════════════════════════════════════════════════════
// WEBSOCKET SERVER SETUP
// ═══════════════════════════════════════════════════════════════

export function setupWebSocketServer(server: any, path: string = '/ws'): WebSocketServer {
  wss = new WebSocketServer({ 
    server,
    path,
    clientTracking: true
  });

  wss.on('connection', (socket: WebSocket, req) => {
    const clientId = `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const connection: ClientConnection = {
      id: clientId,
      socket,
      subscriptions: [],
      connectedAt: new Date(),
      lastPing: new Date(),
      metadata: {
        ip: req.socket.remoteAddress,
        userAgent: req.headers['user-agent']
      }
    };

    realtimeHub.addConnection(connection);

    // Send welcome message
    socket.send(JSON.stringify({
      type: 'CONNECTED',
      clientId,
      timestamp: Date.now(),
      message: 'Connected to TA Engine Real-time API'
    }));

    // Handle messages
    socket.on('message', (data) => {
      try {
        const message = JSON.parse(data.toString());
        handleClientMessage(clientId, message, socket);
      } catch (err) {
        socket.send(JSON.stringify({
          type: 'ERROR',
          message: 'Invalid JSON message'
        }));
      }
    });

    // Handle ping
    socket.on('pong', () => {
      realtimeHub.updatePing(clientId);
    });

    // Handle close
    socket.on('close', () => {
      realtimeHub.removeConnection(clientId);
    });

    // Handle error
    socket.on('error', (err) => {
      console.error(`[WebSocket] Error for client ${clientId}:`, err.message);
    });
  });

  // Heartbeat interval
  const heartbeatInterval = setInterval(() => {
    wss?.clients.forEach((socket) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.ping();
      }
    });
  }, 30000);

  wss.on('close', () => {
    clearInterval(heartbeatInterval);
  });

  console.log(`[WebSocket] Server started on path ${path}`);
  return wss;
}

// ═══════════════════════════════════════════════════════════════
// MESSAGE HANDLING
// ═══════════════════════════════════════════════════════════════

interface ClientMessage {
  action: 'SUBSCRIBE' | 'UNSUBSCRIBE' | 'PING' | 'GET_STATS' | 'GET_RECENT' | 'subscribe' | 'unsubscribe';
  subscriptionId?: string;
  filter?: SubscriptionFilter;
  channel?: ChannelName;
  symbol?: string;
  limit?: number;
}

function handleClientMessage(clientId: string, message: ClientMessage, socket: WebSocket): void {
  const action = (message.action || '').toUpperCase();

  switch (action) {
    case 'SUBSCRIBE': {
      // Channel-based subscription (simplified API)
      if (message.channel) {
        const channelFilter = resolveChannelFilter(message.channel, message.symbol);
        if (!channelFilter) {
          socket.send(JSON.stringify({
            type: 'ERROR',
            message: `Unknown channel: ${message.channel}. Available: ${ALL_CHANNELS.join(', ')}`
          }));
          return;
        }

        const subscription = realtimeHub.subscribe(clientId, channelFilter);
        if (subscription) {
          socket.send(JSON.stringify({
            type: 'SUBSCRIBED',
            channel: message.channel,
            symbol: message.symbol || '*',
            subscriptionId: subscription.id,
            eventTypes: channelFilter.eventTypes,
            timestamp: Date.now()
          }));
        }
        return;
      }

      // Filter-based subscription (advanced API)
      const filter = message.filter || {};
      const subscription = realtimeHub.subscribe(clientId, filter);
      
      if (subscription) {
        socket.send(JSON.stringify({
          type: 'SUBSCRIBED',
          subscriptionId: subscription.id,
          filter: subscription.filter,
          timestamp: Date.now()
        }));
      } else {
        socket.send(JSON.stringify({
          type: 'ERROR',
          message: 'Failed to create subscription'
        }));
      }
      break;
    }

    case 'UNSUBSCRIBE': {
      if (message.subscriptionId) {
        const success = realtimeHub.unsubscribe(message.subscriptionId);
        socket.send(JSON.stringify({
          type: 'UNSUBSCRIBED',
          subscriptionId: message.subscriptionId,
          success,
          timestamp: Date.now()
        }));
      }
      break;
    }

    case 'PING': {
      realtimeHub.updatePing(clientId);
      socket.send(JSON.stringify({
        type: 'PONG',
        timestamp: Date.now()
      }));
      break;
    }

    case 'GET_STATS': {
      const stats = realtimeHub.getStats();
      socket.send(JSON.stringify({
        type: 'STATS',
        data: stats,
        timestamp: Date.now()
      }));
      break;
    }

    case 'GET_RECENT': {
      const events = realtimeHub.getRecentEvents(message.limit || 50, message.filter);
      socket.send(JSON.stringify({
        type: 'RECENT_EVENTS',
        data: events,
        timestamp: Date.now()
      }));
      break;
    }

    default:
      socket.send(JSON.stringify({
        type: 'ERROR',
        message: `Unknown action: ${message.action}. Supported: subscribe, unsubscribe, PING, GET_STATS, GET_RECENT`
      }));
  }
}

// ═══════════════════════════════════════════════════════════════
// BROADCAST HELPERS
// ═══════════════════════════════════════════════════════════════

/**
 * Broadcast to all connected clients
 */
export function broadcastToAll(event: RealtimeEvent): void {
  if (!wss) return;

  const message = JSON.stringify(event);
  
  wss.clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(message);
    }
  });
}

/**
 * Get WebSocket server stats
 */
export function getWebSocketStats(): { connected: number; ready: number } {
  if (!wss) return { connected: 0, ready: 0 };

  let ready = 0;
  wss.clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) ready++;
  });

  return {
    connected: wss.clients.size,
    ready
  };
}

/**
 * Close WebSocket server
 */
export function closeWebSocketServer(): Promise<void> {
  return new Promise((resolve) => {
    if (wss) {
      wss.close(() => {
        console.log('[WebSocket] Server closed');
        resolve();
      });
    } else {
      resolve();
    }
  });
}
