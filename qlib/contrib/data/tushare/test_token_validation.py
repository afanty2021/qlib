#!/usr/bin/env python3
"""
TuShare Token验证测试

验证Token的有效性和格式。
"""

import os
import sys
import requests
import json

# 添加Qlib路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from qlib.contrib.data.tushare import TuShareConfig


def test_token_format():
    """测试Token格式"""
    print("🔍 Token格式验证")
    print("=" * 40)

    try:
        # 从配置文件加载
        config = TuShareConfig.from_file("demo_tushare_config.json")
        token = config.token

        print(f"Token: {token}")
        print(f"Token长度: {len(token)}")

        # TuShare Token通常是40位字符
        if len(token) == 40:
            print("✅ Token长度正确 (40位)")
        else:
            print(f"⚠️ Token长度异常，期望40位，实际{len(token)}位")

        # Token应该只包含字母和数字
        if token.isalnum():
            print("✅ Token字符格式正确 (仅包含字母和数字)")
        else:
            print("⚠️ Token包含特殊字符")

        return token

    except Exception as e:
        print(f"❌ Token加载失败: {e}")
        return None


def test_token_direct_api():
    """直接测试Token API调用"""
    print("\n🌐 直接API测试")
    print("=" * 40)

    try:
        config = TuShareConfig.from_file("demo_tushare_config.json")
        token = config.token

        # 直接调用TuShare API
        url = f"{config.api_url}/trade_cal"
        params = {
            "token": token,
            "exchange": "SSE",
            "start_date": "20240101",
            "end_date": "20240110",
            "is_open": "1"
        }

        print(f"请求URL: {url}")
        print(f"请求参数: {params}")

        response = requests.post(url, json=params, timeout=10)

        print(f"HTTP状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")

        if response.status_code == 200:
            try:
                data = response.json()
                print(f"API响应结构: {list(data.keys())}")

                if data.get("code") == 0:
                    print("✅ API调用成功")
                    if "data" in data and data["data"]:
                        print(f"数据条数: {len(data['data'])}")
                        print(f"示例数据: {data['data'][:2]}")
                    else:
                        print("⚠️ 返回数据为空")
                else:
                    print(f"❌ API返回错误: {data.get('msg', '未知错误')}")
                    print(f"错误代码: {data.get('code')}")

            except json.JSONDecodeError:
                print("❌ 响应不是有效的JSON格式")
                print(f"原始响应: {response.text[:200]}...")
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")
            print(f"错误信息: {response.text[:200]}...")

    except requests.exceptions.Timeout:
        print("❌ 请求超时")
    except requests.exceptions.ConnectionError:
        print("❌ 网络连接错误")
    except Exception as e:
        print(f"❌ 测试失败: {e}")


def test_tushare_token_info():
    """获取Token信息"""
    print("\n📋 Token信息查询")
    print("=" * 40)

    try:
        config = TuShareConfig.from_file("demo_tushare_config.json")
        token = config.token

        # 调用token接口查询信息
        url = f"{config.api_url}/token"
        params = {
            "token": token
        }

        response = requests.post(url, json=params, timeout=10)

        if response.status_code == 200:
            data = response.json()

            if data.get("code") == 0:
                print("✅ Token信息查询成功")
                token_data = data.get("data", {})
                print("Token信息:")
                for key, value in token_data.items():
                    print(f"  {key}: {value}")
            else:
                print(f"❌ Token信息查询失败: {data.get('msg', '未知错误')}")
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")

    except Exception as e:
        print(f"❌ Token信息查询失败: {e}")


def main():
    """主函数"""
    print("🧪 TuShare Token验证测试")
    print("=" * 60)

    # 检查配置文件
    if not os.path.exists("demo_tushare_config.json"):
        print("❌ 未找到配置文件 demo_tushare_config.json")
        print("请确保配置文件存在且包含有效的Token")
        return

    # 测试Token格式
    token = test_token_format()

    if not token:
        print("\n❌ Token验证失败")
        return

    # 测试直接API调用
    test_token_direct_api()

    # 查询Token信息
    test_tushare_token_info()

    print("\n💡 如果Token验证失败，请检查:")
    print("1. Token是否正确复制（没有多余的空格或换行）")
    print("2. Token是否已过期或被禁用")
    print("3. 账户是否有足够的积分调用API")
    print("4. 网络连接是否正常")
    print("5. 是否在TuShare官网申请了有效的API Token")


if __name__ == "__main__":
    main()