#!/usr/bin/env python3
"""
Token修复工具

清理和验证TuShare Token格式。
"""

import os
import sys
import json
import re

# 添加Qlib路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from qlib.contrib.data.tushare import TuShareConfig


def clean_token(token):
    """清理Token"""
    if not token:
        return None

    # 移除前缀和后缀
    token = token.strip()

    # 移除常见的前缀
    prefixes_to_remove = ["demo_", "test_", "token_", "tushare_"]
    for prefix in prefixes_to_remove:
        if token.lower().startswith(prefix):
            token = token[len(prefix):]
            break

    # 提取40位字母数字部分
    # 使用正则表达式找到40位的字母数字字符串
    match = re.search(r'[a-zA-Z0-9]{40}', token)
    if match:
        cleaned_token = match.group(0)
        print(f"原始Token: {token}")
        print(f"清理后Token: {cleaned_token}")
        print(f"Token长度: {len(cleaned_token)}")
        return cleaned_token

    return None


def fix_config_file():
    """修复配置文件"""
    print("🔧 修复配置文件中的Token")
    print("=" * 40)

    try:
        # 读取配置文件
        with open("demo_tushare_config.json", 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        original_token = config_data.get("token", "")
        print(f"原始Token: {original_token}")

        # 清理Token
        cleaned_token = clean_token(original_token)

        if not cleaned_token:
            print("❌ 无法从原始Token中提取有效的40位Token")
            return False

        if len(cleaned_token) != 40:
            print(f"❌ 清理后的Token长度不正确: {len(cleaned_token)}")
            return False

        # 更新配置
        config_data["token"] = cleaned_token

        # 写回配置文件
        with open("demo_tushare_config.json", 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Token已修复并更新到配置文件")
        print(f"新Token: {cleaned_token}")
        return True

    except Exception as e:
        print(f"❌ 配置文件修复失败: {e}")
        return False


def test_fixed_token():
    """测试修复后的Token"""
    print("\n🧪 测试修复后的Token")
    print("=" * 40)

    try:
        # 重新加载配置
        config = TuShareConfig.from_file("demo_tushare_config.json")
        token = config.token

        print(f"Token: {token}")
        print(f"长度: {len(token)}")

        # 验证格式
        if len(token) == 40 and token.isalnum():
            print("✅ Token格式正确")

            # 简单的API测试
            import requests

            url = f"{config.api_url}/token"
            params = {"token": token}

            response = requests.post(url, json=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    print("✅ Token验证成功")
                    token_info = data.get("data", {})
                    if token_info:
                        print("Token信息:")
                        for key, value in token_info.items():
                            print(f"  {key}: {value}")
                else:
                    print(f"❌ Token验证失败: {data.get('msg')}")
            else:
                print(f"❌ HTTP请求失败: {response.status_code}")

        else:
            print("❌ Token格式仍然不正确")

    except Exception as e:
        print(f"❌ 测试失败: {e}")


def main():
    """主函数"""
    print("🛠️ TuShare Token修复工具")
    print("=" * 60)

    if not os.path.exists("demo_tushare_config.json"):
        print("❌ 未找到配置文件 demo_tushare_config.json")
        return

    print("发现Token格式问题:")
    print("- 当前Token包含前缀或特殊字符")
    print("- TuShare Token应该是40位字母数字字符串")
    print()

    # 确认是否修复
    response = input("是否自动修复Token格式? (y/n): ").lower().strip()

    if response in ['y', 'yes']:
        if fix_config_file():
            test_fixed_token()
        else:
            print("❌ Token修复失败")
    else:
        print("❌ 用户取消修复操作")

    print("\n💡 如果自动修复失败，请手动:")
    print("1. 访问TuShare官网获取正确的Token")
    print("2. 确保Token是40位的字母数字字符串")
    print("3. 更新配置文件中的token字段")


if __name__ == "__main__":
    main()