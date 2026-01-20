import asyncio

from app.runtime.toolkits.base import Toolkit, ToolkitCall, ToolkitResult


class DemoToolkit(Toolkit):
    name = "demo"

    async def run(self, call: ToolkitCall) -> ToolkitResult:
        await asyncio.sleep(0.05)
        return ToolkitResult(
            name=self.name,
            output={
                "echo": call.input,
                "message": "demo toolkit executed",
            },
        )
