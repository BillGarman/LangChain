from __future__ import annotations

from typing import TYPE_CHECKING, List, Literal, Optional

from pydantic import Field

from langchain.agents.agent_toolkits.base import BaseToolkit
from langchain.tools import BaseTool
from langchain.tools.ainetwork.app import AINAppOps
from langchain.tools.ainetwork.owner import AINOwnerOps
from langchain.tools.ainetwork.rule import AINRuleOps
from langchain.tools.ainetwork.set_function import AINSetFunction
from langchain.tools.ainetwork.transfer import AINTransfer
from langchain.tools.ainetwork.utils import authenticate
from langchain.tools.ainetwork.value import AINValueOps

if TYPE_CHECKING:
    from ain.ain import Ain
else:
    try:
        # We do this so pydantic can resolve the types when instantiating
        from ain.ain import Ain
    except ImportError:
        pass


class AINetworkToolkit(BaseToolkit):
    """Toolkit for interacting with AINetwork Blockchain."""

    network: Optional[Literal["mainnet", "testnet"]] = Field("mainnet")
    interface: Optional[Ain] = Field(None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.interface:
            self.interface = authenticate(network=self.network)

    class Config:
        """Pydantic config."""

        validate_all = True
        arbitrary_types_allowed = True

    def get_tools(self) -> List[BaseTool]:
        """Get the tools in the toolkit."""
        return [
            AINAppOps(interface=self.interface),
            AINOwnerOps(interface=self.interface),
            AINRuleOps(interface=self.interface),
            AINSetFunction(interface=self.interface),
            AINTransfer(interface=self.interface),
            AINValueOps(interface=self.interface),
        ]
