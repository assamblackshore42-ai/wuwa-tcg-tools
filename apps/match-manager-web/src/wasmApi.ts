import init, * as wasm from '../../../crates/match-core-wasm/pkg/match_core_wasm';

let ready: Promise<typeof wasm> | undefined;

export function loadWasm(): Promise<typeof wasm> {
  ready ??= init()
    .then(() => wasm)
    .catch((error: unknown) => {
      ready = undefined;
      throw error;
    });
  return ready;
}
