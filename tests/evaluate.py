"""
AgentForge 自动化评估脚本
用法： python tests/evaluate.py
"""

import asyncio
import httpx
import json
import time
from datetime import datetime
from typing import Any, Dict, List
import os
import sys  #提供与解释器本身交互的功能

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from unicodedata import category

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#往上两级到项目根目录

BASE_URL = "http://localhost:8000"
API_KEY = "test"

class Evaluator:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=120.0, trust_env=False)  #两分钟超时
        self.results = []  #把这两个属性加到self身上（揣到自己包里），如果不加就是局部变量，执行完函数就没了

    async def call_task_api(self, question: str) -> Dict[str, Any]:
        """调用任务API"""
        url = f"{BASE_URL}/api/v1/tasks/plan"
        payload = {"message": question} #payload:有效载荷（就是载具上的货物）

        try:
            response = await self.client.post(url, json=payload)
            if response.status_code < 400:
                data = response.json()
                return {
                    "success": True,
                    "task_id": data.get("id"),
                    "status": data.get("status"),
                    "output": data.get("output", ""),
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "task_id": None,
                    "status": "failed",
                    "output": "",
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                "success": False,
                "task_id": None,
                "status": "failed",
                "output": "",
                "error": str(e)
            }

    async def get_task_trace(self, task_id: str) -> Dict[str, Any]:
        """获取任务轨迹"""
        url = f"{BASE_URL}/api/v1/tasks/{task_id}/trace"
        try:
            response = await self.client.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def check_keywords(self, output: str, expected_keywords: List[str]) -> bool:
        """检查输出是都包含期望的关键词"""
        output_lower = output.lower()
        for keyword in expected_keywords:
            if keyword.lower() not in output_lower:
                return False
        return True

    async def evaluate_test_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """评估单个测试用例"""
        case_id = test_case["id"]
        category = test_case["category"]  #类别
        question = test_case["question"]
        expected_keywords = test_case.get("expected_keywords", [])

        print(f"正在测试[{case_id}] {category}: {question[:30]}...")

        start_time = time.time()
        response = await self.call_task_api(question)
        elapsed = time.time() - start_time

        result={
            "id": case_id,
            "category": category,
            "question": question,
            "success": response["success"],
            "status": response["status"],
            "output": response["output"][:500] if response["output"] else "",  # 截断
            "elapsed_seconds": elapsed,
            "error": response["error"]
        }

        #检查关键词
        if response["success"] and response["output"]:
            keyword_match = self.check_keywords(response["output"], expected_keywords)
            result["keywords_match"]=keyword_match  #match:匹配

            #获取trace
            if response.get("task_id"):
                trace = await self.get_task_trace(response["task_id"])
                if trace and "total_tokens" in trace:
                    result["total_tokens"] = trace.get("total_tokens", 0)
                    result["total_nodes"] = trace.get("total_nodes", 0)
        else:
            result["keywords_match"] = False
            result["total_tokens"] = 0
            result["total_nodes"] = 0

        result["overall_success"] = response["success"] and result.get("keywords_match", False)

        status_icon = "✅️" if result["overall_success"] else "❌️"
        #icon:图标
        print(f"   {status_icon} 完成，成功：{result['overall_success']}, 耗时: {elapsed:.2f}s")#保留两位小数

        return result

    async def run_evaluation(self, test_file: str):
        """运行完整评估"""
        #1.加载测试用例
        with open(test_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            test_cases = data["test_cases"]

        print(f"\n🚀开始评估，共{len(test_cases)}个测试用例")
        print("=" * 60)

        #逐个执行（串行，避免压垮服务）
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n[{i}/{len(test_cases)}] 测试中...")
            result = await self.evaluate_test_case(test_case)
            self.results.append(result)

            #每隔5个打印一次汇总
            if i % 5 == 0:
                success_count = sum(1 for r in self.results if r["overall_success"])
                print(f"\n 当前进度: {i}/{len(test_cases)}, 成功率: {success_count}/{i} ({success_count / i * 100:.1f}%)")

        #3.关闭客户端
        await self.client.aclose()

        #4.生成报告
        self.generate_report()

    def generate_report(self):
        """生成评估报告"""
        total = len(self.results)
        success_count = sum(1 for r in self.results if r["overall_success"])

        #按分类统计
        categories = {}
        for r in self.results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "success": 0}
            categories[cat]["total"] += 1
            if r["overall_success"]:
                categories[cat]["success"] += 1

            #计算平均耗时
            avg_elapsed = sum(r["elapsed_seconds"] for r in self.results) / total if total > 0 else 0
            #总Token
            total_tokens = sum(r.get("total_tokens", 0) for r in self.results)

            # 打印报告
            print("\n" + "=" * 60)
            print(" 评估报告")
            print("=" * 60)
            print(f"总测试用例: {total}")
            print(f"成功数量: {success_count}")
            print(f"成功率: {success_count / total * 100:.2f}%")
            print(f"平均耗时: {avg_elapsed:.2f} 秒")
            print(f"总 Token 消耗: {total_tokens}")
            print(f"\n按分类统计:")
            for cat, stats in categories.items():
                print(
                    f"  - {cat}: {stats['success']}/{stats['total']} ({stats['success'] / stats['total'] * 100:.1f}%)")

            #失败案例分析
            failed = [r for r in self.results if not r["overall_success"]]
            if failed:
                print(f"\n❌ 失败案例 ({len(failed)} 个):")
                for r in failed[:5]:  #只显示前五个
                    print(f"  - [{r['id']}] {r['question'][:40]}...")
                    if r["error"]:
                        print(f"    错误: {r['error'][:100]}")

            #保存详细报告
            report = {
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total": total,
                    "success": success_count,
                    "success_rate": success_count / total * 100,
                    "avg_elapsed": avg_elapsed,
                    "total_tokens": total_tokens
                },
                "categories": categories,
                "details": self.results
            }

            report_file = f"tests/evaluation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

            print(f"\n📄 详细报告已保存到: {report_file}")



async def wait_for_service(retries=5, delay=2) -> bool:
    """等 backend 就绪:最多重试 retries 次,每次间隔 delay 秒"""
    async with httpx.AsyncClient(trust_env=False) as client:
        for i in range(retries):
            try:
                r = await client.get("http://localhost:8000/health", timeout=5)
                if r.status_code == 200:
                    return True
            except Exception as e:
                print(f"  健康检查异常: {type(e).__name__}: {e}")
            print(f"服务未就绪,{delay}秒后重试({i + 1}/{retries})...")
            await asyncio.sleep(delay)
    return False

async def main():
    """主流程:先等服务就绪,再跑评估"""
    if not await wait_for_service():
        print("❌ 无法连接到服务，请确保 docker-compose 已启动")
        return
    #运行评估
    evaluator = Evaluator()
    await evaluator.run_evaluation("tests/test_questions.json")

if __name__ == '__main__':
    asyncio.run(main())