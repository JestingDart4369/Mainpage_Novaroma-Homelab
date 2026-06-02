@echo off
docker build -t novaroma-mainpage .
docker run --rm -p 8000:8000 novaroma-mainpage
