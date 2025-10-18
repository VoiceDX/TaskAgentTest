#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse

def main():
    parser = argparse.ArgumentParser(
        description="要件: -rで渡した文章 と 実行時に入力した文章 を改行して順に表示します。"
    )
    # -r で単一の文章を受け取る（スペースを区切りとしない）
    parser.add_argument(
        "-r",
        "--raw",
        type=str,
        required=True,
        help="自然言語で記述された文章（例: -r 今日は良い天気です）"
    )
    args = parser.parse_args()

    # 要件2: ユーザ入力を受け付ける
    try:
        user_input = input("文章を入力してください: ")
    except EOFError:
        user_input = ""

    # 要件3: 引数の文章と入力文章を改行して順に表示
    print(args.raw)
    print(user_input)

if __name__ == "__main__":
    main()
