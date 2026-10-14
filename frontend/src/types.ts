/** The small part of Home Assistant's frontend objects that the card uses. */

export interface HassEntity {
  state: string;
  attributes: Record<string, unknown>;
}

export interface HomeAssistant {
  states: Record<string, HassEntity>;
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
