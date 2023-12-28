# agents-for-bedrock-sample

## セットアップ

* AWS CLIのインストール

  ```shell
  pushd /tmp
  wget https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -O awscliv2.zip
  unzip -q awscliv2.zip
  sudo ./aws/install
  aws --version
  popd
  ```

* SAM CLIのインストール

  ```shell
  pushd /tmp
  wget https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip
  unzip -q aws-sam-cli-linux-x86_64.zip -d sam-installation
  sudo ./sam-installation/install
  sam --version
  popd
  ```

* 認証情報の設定

  ```shell
  aws configure --profile me
  ```

## 開発

* Start FastAPI

  ```shell
  cd agents
  pip install -r requirements.txt
  pip install boto3
  uvicorn app:app --reload
  ```

* OpenAPI Docs

  http://localhost:8000/docs

## ビルド・デプロイ

* 初回

  1. `./build.sh`
  1. `sam deploy --guided`
  1. `./deploy.sh`
  1. マネジメントコンソールでAgents for Amazon Bedrockを作成
  1. .env.exampleを参考に.envを作成
  1. `./deploy.sh`
  1. マネジメントコンソールでテスト

* 2回目以降

  1. `./build.sh`
  1. `./deploy.sh`
  1. マネジメントコンソールでテスト
