# match-core-wasm

`match-core` をブラウザから使うJSONバインディングです。保存先・UI・HTTPに依存しません。

| API                    | 入力                                | 出力                                         |
| ---------------------- | ----------------------------------- | -------------------------------------------- |
| `initial_state`        | なし                                | 初期状態のJSON                               |
| `apply_command`        | 状態JSON、コマンドJSON              | `{ changed, state }` のJSON                  |
| `undo_state`           | 現在状態JSON、復元候補JSON          | revisionを更新した復元状態のJSON             |
| `history_cutoff_index` | 新しい順のリセット履歴index配列JSON | 保持する最古対戦の境界index、またはundefined |

入力エラーはJavaScript側の例外として返します。
状態を検証し、revisionをJavaScriptの安全な整数範囲に制限します。
Undoの履歴読込と削除、候補状態の保存は呼出側のアダプターが担当します。

```powershell
pnpm match-core:wasm
```

`wasm-pack --target web` でES ModuleとWasmと型定義を `pkg/` に生成します。
ビルドはCargo.lockで依存を固定し、wasm-optは工程2では追加ツール取得を避けるため無効です。
初期化は非同期で一度実行してからAPIを使用します。
生成物はViteの配布ビルドに含め、ブラウザ内で実行します。サーバー上のWasmではありません。

自作部分は[MITライセンス](LICENSE)です。
