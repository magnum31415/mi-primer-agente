
uv init mi-primer-agente

uv add --dev ipykernel
uv run python -c "import ipykernel; print(ipykernel.__version__)"


Componente	Responsabilidad
LangGraph	Orquesta nodos, estados y decisiones.
LangChain	Ofrece integraciones y abstracciones para trabajar con LLM y herramientas.
LLM	Interpreta los datos y genera el diagnóstico.

uv add langgraph
uv add langgraph langchain-openai