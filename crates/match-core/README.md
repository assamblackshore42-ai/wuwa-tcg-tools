# match-core

DesktopとWebで共有する、保存先に依存しないRustの対戦コアです。
対戦状態・コマンド・ライフ・戦況・ターンの状態遷移、保存状態の検証、Undoのrevision更新、直近50戦の履歴境界を扱います。
依存はserdeのみで、Tauri、SQLite、HTTP、ブラウザAPIには依存しません。

`MatchState::apply` は状態を変更したかを返します。保存アダプターは候補状態に適用し、変更があった場合だけ状態と履歴をトランザクションで保存します。
`restore_undo` は直前の履歴またはbaselineから復元する状態を計算します。履歴が空の場合は呼ばず、最新履歴の削除と状態保存はアダプターが担当します。
`history_cutoff` には状態を変更したリセットを新しい順で渡します。返された境界の状態をbaselineに保存し、その境界を含む古い履歴を削除します。
`MatchState::validate` は保存データのライフ範囲、プレイヤーの並び、ターン番号を検証します。

リポジトリのルートで実行します。

```powershell
pnpm match-core:format
pnpm match-core:check
pnpm match-core:test
pnpm match-manager:rust:test
```

共有crateは `crates/Cargo.toml` のworkspaceで管理します。
Desktopは既存の独立したCargoプロジェクトのままpath依存で利用し、既存のtargetパス、Cargo.lock、Tauriのrelease profileを維持します。
Wasmラッパーは後続工程でこのworkspaceに追加します。

自作部分は[MITライセンス](LICENSE)です。
