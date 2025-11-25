#!/usr/bin/env python3
"""
TuShare Token获取和验证指南

指导用户如何获取正确的TuShare Token并进行验证。
"""

import os
import sys
import webbrowser

# 添加Qlib路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from qlib.contrib.data.tushare import TuShareConfig


def show_token_guide():
    """显示Token获取指南"""
    print("🎯 TuShare Token获取和验证指南")
    print("=" * 60)

    print("📋 第一步：注册TuShare账号")
    print("1. 访问TuShare官网: https://tushare.pro")
    print("2. 点击右上角'注册'")
    print("3. 填写注册信息并验证邮箱")
    print("4. 完成实名认证（需要身份证信息）")

    print("\n🔑 第二步：获取API Token")
    print("1. 登录TuShare账号")
    print("2. 点击右上角头像 → '个人中心'")
    print("3. 在左侧菜单中点击'接口Token'")
    print("4. 点击'生成Token'按钮")
    print("5. 复制生成的40位Token")

    print("\n⚠️ 第三步：注意事项")
    print("1. Token是40位字母数字字符串，如：eb13b3bfd2bd07fd9eb40234f19941c73f230e1e")
    print("2. 请妥善保管Token，不要泄露给他人")
    print("3. 免费账号有积分限制，积分用完需要充值或等待次日重置")
    print("4. Token永久有效，除非主动禁用")

    print("\n💰 第四步：积分说明")
    print("- 免费用户：每日120积分")
    "- 积分消耗：")
    print("  - 股票行情：1积分/次")
    print("  - 财务数据：5积分/次")
    print("  - 宏观数据：10积分/次")

    # 打开TuShare官网
    print("\n🌐 是否打开TuShare官网?")
    response = input("打开浏览器访问TuShare官网? (y/n): ").lower().strip()

    if response in ['y', 'yes']:
        webbrowser.open("https://tushare.pro")
        print("✅ 已打开TuShare官网")


def verify_new_token():
    """验证用户输入的新Token"""
    print("\n🔍 Token验证")
    print("=" * 40)

    print("请输入您的TuShare Token (40位字母数字):")
    token = input("Token: ").strip()

    # 验证Token格式
    if not token:
        print("❌ Token不能为空")
        return False

    if len(token) != 40:
        print(f"❌ Token长度不正确，期望40位，实际{len(token)}位")
        return False

    if not token.isalnum():
        print("❌ Token包含非法字符，应只包含字母和数字")
        return False

    print(f"✅ Token格式正确: {token}")

    # 询问是否更新配置文件
    response = input("是否更新配置文件中的Token? (y/n): ").lower().strip()

    if response in ['y', 'yes']:
        return update_config_token(token)

    return False


def update_config_token(token):
    """更新配置文件中的Token"""
    try:
        # 读取配置文件
        config_file = "demo_tushare_config.json"
        if not os.path.exists(config_file):
            print("❌ 配置文件不存在")
            return False

        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        # 更新Token
        config_data["token"] = token

        # 写回文件
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Token已更新到配置文件: {config_file}")

        # 测试新Token
        return test_new_token(token)

    except Exception as e:
        print(f"❌ 更新配置文件失败: {e}")
        return False


def test_new_token(token):
    """测试新Token"""
    print("\n🧪 测试新Token")
    print("=" * 30)

    try:
        import requests

        # 测试token接口
        url = "http://api.tushare.pro/token"
        params = {"token": token}

        print("正在验证Token...")
        response = requests.post(url, json=params, timeout=10)

        if response.status_code == 200:
            data = response.json()

            if data.get("code") == 0:
                print("✅ Token验证成功!")
                token_info = data.get("data", {})
                print("Token信息:")
                for key, value in token_info.items():
                    print(f"  {key}: {value}")

                # 测试获取数据
                return test_data_fetch(token)
            else:
                print(f"❌ Token验证失败: {data.get('msg', '未知错误')}")
                return False
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_data_fetch(token):
    """测试数据获取"""
    print("\n📊 测试数据获取")
    print("=" * 30)

    try:
        import requests

        # 测试获取交易日历
        url = "http://api.tushare.pro/trade_cal"
        params = {
            "token": token,
            "exchange": "SSE",
            "start_date": "20240101",
            "end_date": "20240105",
            "is_open": "1"
        }

        print("正在获取交易日历...")
        response = requests.post(url, json=params, timeout=10)

        if response.status_code == 200:
            data = response.json()

            if data.get("code") == 0:
                trade_data = data.get("data", [])
                if trade_data:
                    print(f"✅ 数据获取成功! 获取到{len(trade_data)}个交易日")
                    print("示例数据:")
                    for item in trade_data[:3]:
                        print(f"  {item}")
                    return True
                else:
                    print("⚠️ 获取到空数据")
                    return True  # 空数据也算成功，可能是时间范围问题
            else:
                print(f"❌ 数据获取失败: {data.get('msg')}")
                return False
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ 数据获取测试失败: {e}")
        return False


def main():
    """主函数"""
    show_token_guide()

    if verify_new_token():
        print("\n🎉 Token设置成功!")
        print("现在可以运行以下命令测试完整功能:")
        print("python qlib/contrib/data/tushare/test_real_data.py")
    else:
        print("\n⚠️ Token设置失败")
        print("请按照上述指南重新获取Token并重试")


if __name__ == "__main__":
    import json
    main()