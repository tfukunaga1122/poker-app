# POKER LEAGUE PRO

ポーカーの結果画面を記録用LINEグループに送ると、OCRで収支と部屋IDを読み取り、既存のGoogleスプレッドシートへ自動記録するアプリです。

## 動作

1. プレイヤーが結果画面の画像をグループLINEに送信します。
2. 公式LINEが送信者のLINEユーザーIDを選手名へ対応付けます。
3. `収支` の符号付き数値と`部屋ID`をOCRで読み取ります。
4. グループごとの換算率でポイントを算出し、`scores` シートへ追記します。
5. その月のグループ全体の合計を返信します。合計が`0`なら一致、異なれば警告を表示します。

未登録グループ・未登録ユーザー・読み取り不能画像・同一メッセージの再送はスコアに記録しません。処理履歴は `ocr_imports` シートに残ります。

## 台帳の構成

既存のシートは変更しません。

- `scores`: `名前`、`スコア`、`リーグ`、`日付`
- `players`: 選手名とリーグ
- `leagues`: リーグ名

初回だけ次のコマンドで、LINE連携用の4シートを追加します。Cloud Runへ配置済みの場合は、起動時に自動追加されます。

```powershell
uv run -m app.bootstrap
```

- `line_users`: LINEユーザーIDと選手名の対応表
- `line_groups`: グループID、リーグ、換算率の対応表
- `ocr_imports`: OCRの受信履歴、重複防止、合計確認用の記録
- `pending_score_inputs`: 画像は認識できたものの収支だけ読めない場合の、LINE手入力待ち一覧

## OCRで収支だけ読めなかった場合

部屋IDまで認識できた場合、画像を再送しなくても、公式LINEが次のように案内します。

```text
入力 -4400
```

結果画面に表示された**換算前**の符号付き収支を送ると、直前に案内された画像に対応する送信者の選手名へ記録します。手入力後も、その月の合計ポイントが0かどうかを通知します。

## 結果画像を撮り忘れた場合

グループの登録済み選手名を指定して、画像なしでも記録できます。

```text
手動入力 たくみ -4400
```

こちらも結果画面に表示される**換算前**の符号付き収支を使います。画像がない場合も、その月の合計ポイントへ反映されます。

## 初期設定

1. Google CloudでSheets APIとCloud Vision APIを有効にします。
2. Cloud Runで使うサービスアカウントにスプレッドシートへの編集権限を付与します。ローカルでは同じサービスアカウントを `GOOGLE_APPLICATION_CREDENTIALS` に設定します。
3. LINE DevelopersでMessaging APIチャネルを作り、グループ参加を許可します。公式LINEを対象グループへ招待します。
4. `.env.example` を参考に、LINEのチャネルシークレットとアクセストークンを実行環境の秘密情報として設定します。
5. `uv run -m app.bootstrap` を一度実行し、追加シートを作成します。
6. `line_groups` に、最初の画像を送った際に `ocr_imports` へ記録される `group_id` とリーグ・換算率を登録します。
7. `line_users` に、同様に確認できる `line_user_id` と選手名・リーグを登録します。

`line_groups` の換算率は、既存アプリと同じ分母です。たとえば 1/30 なら `30` を設定します。元収支 `+62,500` は `+2,080pt` になります。

## ローカル実行

```powershell
uv python install 3.12
uv venv --python 3.12
uv sync
uv run uvicorn app.main:app --reload --port 8080
```

LINEのWebhook URLには、公開したURLの `/callback` を設定します。ローカル確認時はCloud Runなど、LINEからHTTPSで到達できる環境が必要です。

## Cloud Runへの配置

Cloud RunのサービスアカウントにSheets API・Cloud Vision APIの利用権限を付与し、環境変数として `SPREADSHEET_ID`、`LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN` を設定してください。LINEの秘密情報はSecret Managerで管理します。

## 開発上の注意

既存のStreamlit画面はシート全体を書き戻す処理を使用しています。OCRと同時に手入力が発生する場合の競合を避けるため、次の段階で手動登録もバックエンドの行追記APIに統一してください。
