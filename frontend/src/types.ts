/** The small part of Home Assistant's frontend objects that the card uses. */

export interface HassEntity {
  state: string;
  attributes: Record<string, unknown>;
}

/** The websocket connection; only subscribing is used (live todo items). */
export interface HassConnection {
  subscribeMessage<T>(
    callback: (message: T) => void,
    subscribeMessage: Record<string, unknown>,
  ): Promise<() => unknown>;
}

export interface HomeAssistant {
  states: Record<string, HassEntity>;
  connection?: HassConnection;
  /** Language of the logged in user, e.g. "sv" or "en". */
  language: string;
  callService(
    domain: string,
    service: string,
    data?: Record<string, unknown>,
    target?: Record<string, unknown>,
    notifyOnError?: boolean,
    returnResponse?: boolean,
  ): Promise<unknown>;
}

export interface InkopCardConfig {
  type: string;
  title?: string;
}

declare global {
  /** Set at build time from package.json. */
  const __INKOP_VERSION__: string;

  interface Window {
    customCards?: Array<{ type: string; name: string; description: string }>;
  }
}
