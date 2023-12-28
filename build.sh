#!/bin/bash

python agents/export_openapi_schema.py
sam build
