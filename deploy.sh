#!/bin/bash

source .env

if [[ -n "${AWS_PROFILE}" ]]; then
  PROFILE="--profile ${AWS_PROFILE}"
else
  PROFILE=""
fi

aws s3 cp ./open-api-schema.json s3://${S3_BUCKET}/${S3_SCHEMA_DIR}/ ${PROFILE}
sam deploy --no-fail-on-empty-changeset ${PROFILE}

if [[ -n "${AGENT_ID}" ]]; then

  aws lambda add-permission \
   --function-name ${LAMBDA_NAME} \
   --action lambda:InvokeFunction \
   --statement-id agent-${AGENT_ID} \
   --principal bedrock.amazonaws.com \
   --source-arn arn:aws:bedrock:${AWS_REGION}:${AWS_ACCOUNT_ID}:agent/${AGENT_ID} \
   ${PROFILE}

  aws bedrock-agent update-agent-action-group \
  --agent-id ${AGENT_ID} \
  --agent-version ${AGENT_VERSION} \
  --action-group-id ${ACTION_GROUP_ID} \
  --action-group-name ${ACTION_GROUP_NAME} \
  --action-group-executor "lambda=arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${LAMBDA_NAME}" \
  --api-schema "s3={s3BucketName=${S3_BUCKET},s3ObjectKey=${S3_SCHEMA_DIR}/open-api-schema.json}" \
  --no-cli-pager \
  ${PROFILE}

  aws bedrock-agent prepare-agent \
  --agent-id ${AGENT_ID} \
  --no-cli-pager \
  ${PROFILE}
fi