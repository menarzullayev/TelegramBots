import io
import logging
import uuid
from functools import lru_cache

import boto3
import matplotlib
import matplotlib.pyplot as plt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pydantic_settings import BaseSettings

matplotlib.use("Agg")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    s3_endpoint: str = "http://minio:9000"
    s3_bucket: str = "tezmath"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    public_url: str = "http://localhost:9000"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


app = FastAPI(title="TezMath Renderer", version="1.0.0")


class RenderRequest(BaseModel):
    latex: str
    dpi: int = 150
    fontsize: int = 14


class RenderResponse(BaseModel):
    url: str
    filename: str


def latex_to_png(latex_source: str, dpi: int = 150, fontsize: int = 14) -> bytes:
    fig, ax = plt.subplots(figsize=(10, 0.5 + latex_source.count("\n") * 0.4))
    ax.axis("off")
    wrapped = f"${latex_source}$" if not latex_source.strip().startswith("$") else latex_source
    ax.text(
        0.5,
        0.5,
        wrapped,
        ha="center",
        va="center",
        fontsize=fontsize,
        transform=ax.transAxes,
        usetex=False,
    )
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def upload_to_s3(data: bytes, filename: str) -> str:
    settings = get_settings()
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )
    s3.put_object(
        Bucket=settings.s3_bucket,
        Key=f"renders/{filename}",
        Body=data,
        ContentType="image/png",
        ACL="public-read",
    )
    return f"{settings.public_url}/{settings.s3_bucket}/renders/{filename}"


@app.post("/render", response_model=RenderResponse)
async def render_endpoint(req: RenderRequest):
    try:
        png_data = latex_to_png(req.latex, req.dpi, req.fontsize)
        filename = f"{uuid.uuid4()}.png"
        url = upload_to_s3(png_data, filename)
        logger.info(f"Rendered: {filename}")
        return RenderResponse(url=url, filename=filename)
    except Exception as e:
        logger.error(f"Render error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}
