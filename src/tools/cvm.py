import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from src.core.exceptions import ExternalAPIError
from src.core.types import DocumentMetadata, DocumentType
from src.tools.base import BaseTool


class CVMTool(BaseTool):
    """Tool for fetching regulatory documents from CVM (Brazilian Securities Commission)."""

    name = "cvm"
    description = "Fetches regulatory documents, filings, and company information from CVM"

    BASE_URL = "https://dados.cvm.gov.br"
    RAD_URL = "https://www.rad.cvm.gov.br"
    SEARCH_URL = f"{BASE_URL}/dataset/cia-aberta"

    DOCUMENT_TYPE_MAPPING = {
        "DFP": DocumentType.ANNUAL_REPORT,
        "ITR": DocumentType.QUARTERLY_REPORT,
        "FR": DocumentType.RELEVANT_FACT,
        "FCA": DocumentType.OTHER,
        "FRE": DocumentType.OTHER,
        "IPE": DocumentType.EARNINGS_RELEASE,
    }

    async def _execute(self, **kwargs: Any) -> list[dict[str, Any]] | dict[str, Any] | bytes:
        """Execute CVM data retrieval."""
        action = kwargs.get("action", "search")
        ticker = kwargs.get("ticker")
        company_name = kwargs.get("company_name")
        document_type = kwargs.get("document_type")
        year = kwargs.get("year")

        if action == "search":
            return await self._search_documents(
                ticker=ticker,
                company_name=company_name,
                document_type=document_type,
                year=year,
            )
        elif action == "get_company_info" and (ticker or company_name):
            return await self._get_company_info(ticker=ticker, company_name=company_name)
        elif action == "download" and kwargs.get("url"):
            return await self._download_document(kwargs["url"])
        elif action == "list_filings" and ticker:
            return await self._list_filings(ticker, year)
        else:
            raise ExternalAPIError(
                message="Invalid action or missing parameters",
                service=self.name,
            )

    async def _search_documents(
        self,
        ticker: str | None = None,
        company_name: str | None = None,
        document_type: str | None = None,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search for documents in CVM database."""
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            try:
                results: list[dict[str, Any]] = []

                if ticker:
                    rad_results = await self._search_rad(client, ticker, document_type, year)
                    results.extend(rad_results)

                if company_name or (not ticker and not results):
                    open_data_results = await self._search_open_data(
                        client, company_name, document_type, year
                    )
                    results.extend(open_data_results)

                return results

            except httpx.TimeoutException:
                raise ExternalAPIError(
                    message="CVM request timed out",
                    service=self.name,
                )
            except Exception as e:
                raise ExternalAPIError(
                    message=f"Failed to search CVM: {str(e)}",
                    service=self.name,
                )

    async def _search_rad(
        self,
        client: httpx.AsyncClient,
        ticker: str,
        document_type: str | None = None,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search RAD system for company filings."""
        results: list[dict[str, Any]] = []

        try:
            search_url = f"{self.RAD_URL}/ENET/frmConsultaExternaCVM.aspx"
            response = await client.get(search_url)

            if response.status_code != 200:
                return results

            results.append(
                {
                    "source": "RAD",
                    "ticker": ticker.upper(),
                    "search_url": search_url,
                    "note": "RAD system requires interactive search. Use the URL to access documents.",
                    "filters": {
                        "document_type": document_type,
                        "year": year,
                    },
                }
            )

        except Exception as e:
            self.logger.warning("rad_search_error", ticker=ticker, error=str(e))

        return results

    async def _search_open_data(
        self,
        client: httpx.AsyncClient,
        company_name: str | None = None,
        document_type: str | None = None,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search CVM Open Data portal."""
        results: list[dict[str, Any]] = []

        datasets = [
            "cia_aberta-doc-dfp_con",
            "cia_aberta-doc-itr_con",
            "cia_aberta-doc-fre",
            "cia_aberta-doc-fca",
        ]

        for dataset in datasets:
            try:
                url = f"{self.BASE_URL}/api/3/action/package_show?id={dataset}"
                response = await client.get(url)

                if response.status_code != 200:
                    continue

                data = response.json()
                if data.get("success") and data.get("result"):
                    result = data["result"]
                    resources = result.get("resources", [])

                    for resource in resources:
                        resource_name = resource.get("name", "").lower()
                        resource_year = self._extract_year_from_name(resource_name)

                        if year and resource_year and resource_year != year:
                            continue

                        if document_type:
                            doc_type_match = any(
                                dt.lower() in resource_name
                                for dt, mapped in self.DOCUMENT_TYPE_MAPPING.items()
                                if mapped.value == document_type
                            )
                            if not doc_type_match:
                                continue

                        results.append(
                            {
                                "source": "CVM Open Data",
                                "dataset": dataset,
                                "resource_id": resource.get("id"),
                                "name": resource.get("name"),
                                "description": resource.get("description"),
                                "format": resource.get("format"),
                                "url": resource.get("url"),
                                "created": resource.get("created"),
                                "last_modified": resource.get("last_modified"),
                                "year": resource_year,
                            }
                        )

            except Exception as e:
                self.logger.warning("open_data_search_error", dataset=dataset, error=str(e))
                continue

        return results

    def _extract_year_from_name(self, name: str) -> int | None:
        """Extract year from resource name."""
        match = re.search(r"20\d{2}", name)
        if match:
            return int(match.group())
        return None

    async def _get_company_info(
        self,
        ticker: str | None = None,
        company_name: str | None = None,
    ) -> dict[str, Any]:
        """Get company information from CVM."""
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            try:
                url = f"{self.BASE_URL}/api/3/action/package_show?id=cia_aberta-cad"
                response = await client.get(url)

                if response.status_code != 200:
                    raise ExternalAPIError(
                        message="Failed to fetch company registry",
                        service=self.name,
                    )

                data = response.json()
                if not data.get("success"):
                    raise ExternalAPIError(
                        message="Invalid response from CVM",
                        service=self.name,
                    )

                result = data.get("result", {})
                resources = result.get("resources", [])

                csv_resource = next(
                    (r for r in resources if r.get("format", "").upper() == "CSV"),
                    None,
                )

                if csv_resource:
                    return {
                        "source": "CVM Registry",
                        "data_url": csv_resource.get("url"),
                        "format": "CSV",
                        "last_modified": csv_resource.get("last_modified"),
                        "search_params": {
                            "ticker": ticker,
                            "company_name": company_name,
                        },
                        "note": "Download CSV and filter by CODIGO_CVM or DENOM_SOCIAL",
                    }

                return {
                    "source": "CVM Registry",
                    "resources": resources,
                    "search_params": {
                        "ticker": ticker,
                        "company_name": company_name,
                    },
                }

            except ExternalAPIError:
                raise
            except Exception as e:
                raise ExternalAPIError(
                    message=f"Failed to get company info: {str(e)}",
                    service=self.name,
                )

    async def _list_filings(
        self,
        ticker: str,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """List recent filings for a company."""
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            try:
                current_year = year or datetime.now().year
                filings: list[dict[str, Any]] = []

                for doc_type in ["DFP", "ITR", "FR"]:
                    dataset = f"cia_aberta-doc-{doc_type.lower()}_con"
                    url = f"{self.BASE_URL}/api/3/action/package_show?id={dataset}"

                    try:
                        response = await client.get(url)
                        if response.status_code == 200:
                            data = response.json()
                            if data.get("success"):
                                resources = data.get("result", {}).get("resources", [])
                                for resource in resources:
                                    if str(current_year) in resource.get("name", ""):
                                        filings.append(
                                            {
                                                "ticker": ticker.upper(),
                                                "document_type": doc_type,
                                                "year": current_year,
                                                "resource_name": resource.get("name"),
                                                "url": resource.get("url"),
                                                "format": resource.get("format"),
                                            }
                                        )
                    except Exception:
                        continue

                return filings

            except Exception as e:
                raise ExternalAPIError(
                    message=f"Failed to list filings: {str(e)}",
                    service=self.name,
                )

    async def _download_document(self, url: str) -> bytes:
        """Download a document from CVM."""
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                response = await client.get(url, follow_redirects=True)

                if response.status_code != 200:
                    raise ExternalAPIError(
                        message=f"Failed to download document: HTTP {response.status_code}",
                        service=self.name,
                    )

                return response.content

            except httpx.TimeoutException:
                raise ExternalAPIError(
                    message="Document download timed out",
                    service=self.name,
                )
            except Exception as e:
                raise ExternalAPIError(
                    message=f"Failed to download document: {str(e)}",
                    service=self.name,
                )

    def map_document_type(self, cvm_type: str) -> DocumentType:
        """Map CVM document type to internal document type."""
        return self.DOCUMENT_TYPE_MAPPING.get(cvm_type.upper(), DocumentType.OTHER)
