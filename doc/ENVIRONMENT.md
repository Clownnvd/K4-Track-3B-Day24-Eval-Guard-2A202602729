# Môi trường K4 Track 3B

## Phiên bản mục tiêu và cách kiểm tra

Dùng Python 3.11 cho lab này. Tạo virtualenv mới sau khi tải starter, cài
dependencies và chạy `pip check` trên máy của nhóm. Tests hỗ trợ chạy không
cần API hay model; student tests vẫn fail nếu các hàm TODO chưa được làm.

Bộ phiên bản lõi trong starter: RAGAS 0.1.22; LangChain 0.2.17; langchain-core
0.2.43; community 0.2.19; openai integration 0.1.25; OpenAI SDK 1.109.1; NeMo
0.10.0; Annoy 1.17.3; NumPy 1.26.4. Các pins nằm trong `requirements/constraints-core.txt`.
Đây là constraints cho tập lõi, **không phải lock toàn bộ dependencies**.

Trên Windows, build `annoy==1.17.3` cần Microsoft Visual C++ 14.0 trở lên.
Sau khi cài compiler, nhóm chạy các bước kiểm chứng phía dưới trên chính môi
trường sẽ làm lab. Kết quả unit tests hoặc pip resolve không chứng minh full
NeMo đã cài/chạy được.

Theo [README của NeMo v0.10.0](https://github.com/NVIDIA/NeMo-Guardrails/blob/v0.10.0/README.md),
bản này hỗ trợ Python đến 3.11 và cần compiler/dev tools cho Annoy. Không lấy
hướng dẫn bản NeMo mới nhất để suy ra bản 0.10.0 hỗ trợ Python 3.12+.

## Chuẩn bị compiler và virtualenv trước buổi học

Trên Windows, cài Microsoft C++ Build Tools, chọn workload **Desktop development
with C++**, bao gồm MSVC và Windows SDK. Mở lại terminal sau cài; dùng Developer
PowerShell nếu compiler chưa có trong PATH. Làm theo
[hướng dẫn Microsoft](https://learn.microsoft.com/en-us/cpp/build/vscpp-step-0-installation?view=msvc-170).
Việc cài compiler/tải model không thuộc 15 phút kiểm tra đầu buổi.

Từ gốc repo trên PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements/requirements.txt -c requirements/constraints-core.txt
.\.venv\Scripts\python.exe -m pip check
```

Không bắt buộc kích hoạt virtualenv: dùng đường dẫn interpreter như trên.
Nếu muốn chạy `Activate.ps1` và gặp lỗi execution policy, có thể cho phép script
chỉ trong phiên PowerShell hiện tại rồi kích hoạt:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Nếu policy của tổ chức vẫn chặn, dùng interpreter trực tiếp; không thay policy
toàn máy. Xem [hướng dẫn venv Python 3.11](https://docs.python.org/3.11/library/venv.html).
macOS/Linux dùng `python3.11 -m venv .venv` và `source .venv/bin/activate`;
cần toolchain C++ của hệ điều hành khi build Annoy.

## Kiểm chứng cài đặt và tải model

Cài thành công qua pip chưa chứng minh đã tải model hoặc API kết nối được.
Kiểm tra các lớp riêng biệt để biết lỗi nằm ở đâu:

```bash
python -m pip check
python -c "import ragas, nemoguardrails, presidio_analyzer, spacy; print('imports OK')"
python -m spacy download en_core_web_lg
docker compose -f infra/docker-compose.yml up -d
python scripts/setup_answers.py --live
```

Qdrant dùng tag [v1.9.7](https://github.com/qdrant/qdrant/releases/tag/v1.9.7),
không dùng `latest`. Setup sẽ tải embedding BGE-M3/reranker theo module bài
trước; nhóm cần cache/download xong trước lớp. Model/download/indexing có thể
mất lâu tùy máy và mạng. Generation/enrichment có thể gọi API, có chi phí.

Ghi OS, Python, kết quả pip/import/compiler/model download trong TEAM. Nếu full
stack cài chưa xong, ghi lỗi thật; không điền “tương thích” dựa trên dry-run.

## Tạo môi trường unit test offline

Khi chỉ sửa logic/scaffold, không cần cài NeMo, ML model hoặc C++ compiler.
Tạo môi trường riêng với các dependencies đã pin:

```powershell
py -3.11 -m venv .venv-tests
.\.venv-tests\Scripts\python.exe -m pip install -r requirements/requirements-test.lock.txt
.\.venv-tests\Scripts\python.exe -m pip check
.\.venv-tests\Scripts\python.exe -m pytest tests/ -m support -q
```

`requirements/requirements-test.txt` ghi dependencies trực tiếp; file `.lock.txt` khóa
toàn bộ dependencies của tập test. Đây chỉ là lock unit test, không thay constraints hoặc
cài đặt full runtime. Không commit virtualenv, key hoặc cache model.

## Cấu hình đã dùng trên máy Windows này

Môi trường Python 3.11 của lab Day 18 chạy các module m1–m5, Qdrant và RAGAS. Máy
không có MSVC Build Tools nên cài NeMo trực tiếp trên Windows dừng ở bước biên dịch
Annoy. Phase C dùng image Linux `infra/Dockerfile.guard` đã build và kiểm tra
`setup_presidio()` cùng `setup_nemo_rails()` thành công. Image này tải spaCy
`en_core_web_lg`; lần đầu build cần thời gian và dung lượng đáng kể.

Trước khi chạy Phase C, đặt khóa trong **env-file riêng ngoài repo** với các tên
`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_API_BASE`; hai base URL đều trỏ tới
`https://generativelanguage.googleapis.com/v1beta/openai/`. Không commit env-file.
Từ thư mục gốc repo trên PowerShell:

```powershell
docker build -f infra/Dockerfile.guard -t lab24-guard .
docker run --rm --env-file 'C:\path\to\private-env-file' -v "${PWD}:/app" -w /app lab24-guard python scripts/run_experiments.py --phase c --live --latency-samples 20
```

NeMo 0.10.0 mặc định dùng endpoint completions cũ khi tên model không giống GPT;
`setup_nemo_rails()` đăng ký `ChatOpenAI` cho engine `openai_compatible_chat` để dùng
endpoint chat tương thích của Gemini hoặc Groq. Prompt self-check cấp 64 output tokens, vì mức mặc
định 3 tokens từng khiến model trả rỗng và chặn nhầm câu sạch. Tốc độ gọi được
giới hạn theo quota; thời gian chờ quota nằm trong độ trễ đo được của Phase C.

Với bộ nhớ máy này, lần tạo `answers_50q.json` dùng embedding
`sentence-transformers/all-MiniLM-L6-v2` và Flashrank, collection
`lab24_minilm`. BGE-M3 đã được thử và lập chỉ mục 104 đoạn nhưng kết hợp
CrossEncoder không chạy ổn định trong RAM hiện có. Đây là thay đổi cấu hình
thực nghiệm được ghi trong TEAM và báo cáo, không được trình bày như pipeline
BGE-M3 mặc định.

Phase C còn được chạy thật bằng Groq `openai/gpt-oss-120b` qua cùng engine
`openai_compatible_chat`. Khi đổi nhà cung cấp, truyền `GUARD_MODEL` và
`OPENAI_BASE_URL`/`OPENAI_API_BASE` cùng khóa của nhà cung cấp qua biến môi
trường; artifact lưu đúng model của lượt chạy. Presidio English NER nhận nhầm
nhiều cụm tiếng Việt là `PERSON` hoặc `US_DRIVER_LICENSE`, nên `pii_scan`
chỉ dùng các entity bắt buộc của bài: `VN_CCCD`, `VN_PHONE`, `EMAIL_ADDRESS`.
Thay đổi này giúp 8/8 câu sạch qua lớp PII mà vẫn giữ các phép chặn PII thật.

Phase A dùng Groq sau khi khóa Gemini miễn phí chạm giới hạn 500 request/ngày.
`RAGAS_METRIC_MODELS` ánh xạ bốn metric sang ba model Groq như ghi trong
`doc/reports/failure_clusters.md`; `RAGAS_COMPACT_PROMPTS=1` bỏ ví dụ dài trong
prompt evaluator nhưng giữ schema, tiêu chí và phép tính RAGAS 0.1.22. Adapter
chấp nhận JSON list đúng yêu cầu của Faithfulness/Context Recall qua API chat
tương thích và giữ checkpoint từng metric trong `.cache/`. Việc chấm lại các
đáp án ngắn chỉ hoàn chỉnh bước tách câu tiếng Việt; không thay `answer`,
`contexts` hay `ground_truth` trong `answers_50q.json`.
