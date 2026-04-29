import type { TokenError } from './useVoiceToken';

export function TokenForm(props: {
  participantName: string;
  setParticipantName: (v: string) => void;
  roomName?: string;
  setRoomName: (v: string) => void;
  loading: boolean;
  error?: TokenError;
  onConnect: () => void;
}) {
  return (
    <div className="form">
      <div className="grid">
        <label className="field">
          <span className="label">Your name</span>
          <input
            value={props.participantName}
            onChange={(e) => props.setParticipantName(e.target.value)}
            placeholder="User"
            autoComplete="off"
          />
        </label>

        <label className="field">
          <span className="label">Room name (optional)</span>
          <input
            value={props.roomName ?? ''}
            onChange={(e) => props.setRoomName(e.target.value)}
            placeholder="room-123"
            autoComplete="off"
          />
        </label>
      </div>

      {props.error ? (
        <div className="error">
          <div className="errorTitle">Token request failed</div>
          <div className="errorBody">
            <div><b>Status</b>: {props.error.status ?? 'unknown'}</div>
            <div><b>Message</b>: {props.error.message}</div>
          </div>
        </div>
      ) : null}

      <div className="row">
        <button className="btn primary" disabled={props.loading} onClick={props.onConnect}>
          {props.loading ? 'Connecting…' : 'Connect'}
        </button>
        <div className="small">
          This calls <code>/api/token</code> on your backend and uses the returned LiveKit token.
        </div>
      </div>
    </div>
  );
}

