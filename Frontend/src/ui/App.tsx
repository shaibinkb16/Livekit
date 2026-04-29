import { useEffect, useMemo, useState } from 'react';
import {
  type RemoteParticipant,
  Room,
  RoomEvent,
  Track,
  createLocalAudioTrack,
} from 'livekit-client';
import { TokenForm } from './TokenForm';
import { useVoiceToken } from './useVoiceToken';

export function App() {
  const [connected, setConnected] = useState(false);
  const [roomName, setRoomName] = useState<string | undefined>(undefined);
  const [participantName, setParticipantName] = useState('User');
  const [lkRoom, setLkRoom] = useState<Room | null>(null);
  const [remoteParticipants, setRemoteParticipants] = useState<RemoteParticipant[]>([]);
  const [micEnabled, setMicEnabled] = useState(false);

  const { data, error, loading, requestToken, reset } = useVoiceToken();

  const serverUrl = data?.server_url;
  const token = data?.participant_token;

  const title = useMemo(() => {
    if (connected) return `Connected${data?.room_name ? `: ${data.room_name}` : ''}`;
    if (loading) return 'Requesting token…';
    return 'LiveKit Voice Agent';
  }, [connected, data?.room_name, loading]);

  useEffect(() => {
    if (!lkRoom) return;

    const sync = () => setRemoteParticipants(Array.from(lkRoom.remoteParticipants.values()));
    lkRoom.on(RoomEvent.ParticipantConnected, sync);
    lkRoom.on(RoomEvent.ParticipantDisconnected, sync);
    sync();

    return () => {
      lkRoom.off(RoomEvent.ParticipantConnected, sync);
      lkRoom.off(RoomEvent.ParticipantDisconnected, sync);
    };
  }, [lkRoom]);

  return (
    <div className="page">
      <div className="card">
        <div className="header">
          <div>
            <div className="title">{title}</div>
            <div className="subtitle">Backend: <code>{import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'}</code></div>
          </div>
          <div className="actions">
            {connected ? (
              <button
                className="btn secondary"
                onClick={() => {
                  lkRoom?.disconnect();
                  setLkRoom(null);
                  setMicEnabled(false);
                  setConnected(false);
                  reset();
                }}
              >
                Disconnect
              </button>
            ) : null}
          </div>
        </div>

        {!connected ? (
          <TokenForm
            participantName={participantName}
            setParticipantName={setParticipantName}
            roomName={roomName}
            setRoomName={setRoomName}
            loading={loading}
            error={error}
            onConnect={async () => {
              const res = await requestToken({
                room_name: roomName?.trim() ? roomName.trim() : undefined,
                participant_name: participantName.trim() ? participantName.trim() : 'User',
              });
              if (res) setConnected(true);
            }}
          />
        ) : (
          <div className="room">
            {serverUrl && token ? (
              <RoomView
                data={data}
                serverUrl={serverUrl}
                token={token}
                room={lkRoom}
                setRoom={setLkRoom}
                remoteParticipants={remoteParticipants}
                micEnabled={micEnabled}
                setMicEnabled={setMicEnabled}
                onDisconnected={() => {
                  setConnected(false);
                  setLkRoom(null);
                  setMicEnabled(false);
                  reset();
                }}
                onConnected={() => setConnected(true)}
              />
            ) : (
              <div className="error">
                Missing token/server URL. <button className="btn link" onClick={reset}>Back</button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function RoomView(props: {
  data: { room_name: string; agent_name: string };
  serverUrl: string;
  token: string;
  room: Room | null;
  setRoom: (r: Room | null) => void;
  remoteParticipants: RemoteParticipant[];
  micEnabled: boolean;
  setMicEnabled: (v: boolean) => void;
  onConnected: () => void;
  onDisconnected: () => void;
}) {
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const r = new Room();

    r.on(RoomEvent.Connected, () => active && props.onConnected());
    r.on(RoomEvent.Disconnected, () => { if (active) props.onDisconnected(); });
    r.on(RoomEvent.ConnectionStateChanged, (state) => {
      if (!active) return;
      if (state === 'connected') setConnectError(null);
    });

    async function run() {
      setConnecting(true);
      setConnectError(null);
      try {
        await r.connect(props.serverUrl, props.token);
        props.setRoom(r);
      } catch (e) {
        setConnectError(e instanceof Error ? e.message : 'Failed to connect');
        r.disconnect();
        props.setRoom(null);
      } finally {
        setConnecting(false);
      }
    }

    void run();

    return () => {
      active = false;
      r.off(RoomEvent.Connected);
      r.off(RoomEvent.Disconnected);
      r.off(RoomEvent.ConnectionStateChanged);
      r.disconnect();
      props.setRoom(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.serverUrl, props.token]);

  useEffect(() => {
    const r = props.room;
    if (!r) return;

    if (!props.micEnabled) {
      void r.localParticipant.setMicrophoneEnabled(false);
      return;
    }

    // Ensure at least one local mic track exists (Windows sometimes needs this explicit step).
    (async () => {
      try {
        const track = await createLocalAudioTrack();
        await r.localParticipant.publishTrack(track, { source: Track.Source.Microphone });
      } catch {
        // fallback to SDK toggle if direct publish fails
        await r.localParticipant.setMicrophoneEnabled(true);
      }
    })();
  }, [props.micEnabled, props.room]);

  return (
    <div className="roomInner">
      <div className="kv">
        <div>
          <span className="k">Room</span> <span className="v">{props.data.room_name}</span>
        </div>
        <div>
          <span className="k">Agent</span> <span className="v">{props.data.agent_name}</span>
        </div>
        <div>
          <span className="k">Peers</span>{' '}
          <span className="v">{props.remoteParticipants.length}</span>
        </div>
      </div>

      <div className="hint">
        If your agent is configured with dispatch, it should join shortly after you connect.
      </div>

      {connectError ? (
        <div className="error">
          <div className="errorTitle">LiveKit connection failed</div>
          <div className="errorBody">{connectError}</div>
        </div>
      ) : null}

      <div className="row">
        <button
          className="btn primary"
          disabled={connecting || !props.room}
          onClick={() => props.setMicEnabled(!props.micEnabled)}
        >
          {props.micEnabled ? 'Mute mic' : 'Unmute mic'}
        </button>
        <div className="small">You may need to allow microphone permission in the browser.</div>
      </div>

      <AudioRenderer room={props.room} />
    </div>
  );
}

function AudioRenderer(props: { room: Room | null }) {
  useEffect(() => {
    const room = props.room;
    if (!room) return;

    const attached = new Map<string, HTMLAudioElement>();

    function attach(pubId: string, track: Track) {
      const el = track.attach();
      el.autoplay = true;
      document.body.appendChild(el);
      attached.set(pubId, el);
    }

    function detach(pubId: string) {
      const el = attached.get(pubId);
      if (!el) return;
      el.remove();
      attached.delete(pubId);
    }

    room.on(RoomEvent.TrackSubscribed, (track, pub) => {
      if (track.kind === Track.Kind.Audio) attach(pub.trackSid ?? pub.sid, track);
    });
    room.on(RoomEvent.TrackUnsubscribed, (_track, pub) => {
      detach(pub.trackSid ?? pub.sid);
    });

    // attach any already-subscribed tracks
    for (const p of room.remoteParticipants.values()) {
      for (const pub of p.trackPublications.values()) {
        const t = pub.track;
        if (t && t.kind === Track.Kind.Audio) attach(pub.trackSid ?? pub.sid, t);
      }
    }

    return () => {
      for (const el of attached.values()) el.remove();
      attached.clear();
      room.removeAllListeners(RoomEvent.TrackSubscribed);
      room.removeAllListeners(RoomEvent.TrackUnsubscribed);
    };
  }, [props.room]);

  return null;
}

