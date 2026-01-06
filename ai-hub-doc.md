Below is a more detailed document summarizing the “Compiling Models” page from the Qualcomm® AI Hub Workbench documentation. It captures all key sections, including supported formats, target runtimes, and code examples for compiling models to various runtimes.

---

# Qualcomm® AI Hub Workbench – Compiling Models

## Overview

The Qualcomm® AI Hub Workbench allows developers to compile trained models into optimized formats suitable for deployment on devices powered by Snapdragon® processors. The workbench supports multiple model formats and can target a variety of runtime environments.

### Supported Model Formats

The following trained model formats can be compiled in the AI Hub Workbench:

* **PyTorch**: native PyTorch models; must be converted to TorchScript via `torch.jit.trace` or loaded from a saved `.pt`/`.pth` file.
* **ONNX**: widely supported open format.
* **AI Model Efficiency Toolkit (AIMET) quantized models**: quantized models produced by AIMET.
* **TensorFlow (via ONNX)**: compile via an intermediate ONNX representation.

### Target Runtimes

Compiled models can be deployed to several runtime environments:

* **TensorFlow Lite (LiteRT)**: recommended for Android developers; runs on CPU, GPU (via GPU delegation), or NPU (via QNN delegation).
* **ONNX**: recommended for Windows developers.
* **Qualcomm® AI Engine Direct (QNN) context binary**: SoC‑specific; optimized for a single device’s NPU. OS‑agnostic.
* **QNN model library**: operating‑system‑specific `.so` library (e.g., `aarch64_android`); SoC‑agnostic but not ABI‑stable across SDK versions.
* **QNN DLC (Dynamic Library Container)**: hardware‑agnostic container for the QNN runtime.
* A specific version of the AI Engine Direct SDK can be specified using the `--qairt_version` option.

---

## Compiling PyTorch Models

### PyTorch → TensorFlow Lite

1. **Convert to TorchScript**:
   Use `torch.jit.trace(model, example_input)` to generate a TorchScript model. For example:

   ```python
   import torch
   import torchvision
   import qai_hub as hub

   torch_model = torchvision.models.mobilenet_v2(pretrained=True)
   torch_model.eval()

   input_shape = (1, 3, 224, 224)
   example_input = torch.rand(input_shape)
   pt_model = torch.jit.trace(torch_model, example_input)
   ```
2. **Submit Compile Job**:

   ```python
   compile_job = hub.submit_compile_job(
       pt_model,
       name="MobileNet_V2",
       device=hub.Device("Samsung Galaxy S24 (Family)"),
       input_specs={'image': input_shape},
   )
   ```
3. **Download Compiled Model**:

   ```python
   compile_job.download_target_model("MobileNet_V2.tflite")
   ```
4. **Profile Compiled Model (Optional)**:

   ```python
   profile_job = hub.submit_profile_job(
       model=compile_job.get_target_model(),
       device=hub.Device("Samsung Galaxy S24 (Family)")
   )
   ```

> **Alternative**: If you already have a traced or scripted model saved via `torch.jit.save` (e.g., `mobilenet_v2.pt`), pass the file path directly to `submit_compile_job` without tracing.

### PyTorch → QNN Model Library

Use this when you want a `.so` library for deployment on a specific OS architecture:

```python
import qai_hub as hub

compile_job = hub.submit_compile_job(
    model="mobilenet_v2.pt",
    device=hub.Device("Samsung Galaxy S24 (Family)"),
    options="--target_runtime qnn_lib_aarch64_android",
    input_specs={'image': (1, 3, 224, 224)}
)

compile_job.download_target_model("MobileNet_V2.so")
```

**Notes**:

* QNN model libraries are OS‑specific but SoC‑agnostic.
* ABI compatibility is not guaranteed across SDK versions; recompile when upgrading the QNN SDK.

### PyTorch → QNN Context Binary

For device‑specific deployment optimized for the Snapdragon® NPU:

```python
import qai_hub as hub

compile_job = hub.submit_compile_job(
    model="mobilenet_v2.pt",
    device=hub.Device("Samsung Galaxy S24 (Family)"),
    options="--target_runtime qnn_context_binary",
    input_specs={'image': (1, 3, 224, 224)}
)
# Returns a CompileJob instance; download or profile as needed.
```

* The resulting context binary must be deployed on the same device for which it was compiled.
* Context binaries are OS‑agnostic but SoC‑specific.

### PyTorch → ONNX

You can compile a PyTorch model directly to ONNX, producing an optimized `.onnx` file:

```python
import qai_hub as hub

compile_job = hub.submit_compile_job(
    model="mobilenet_v2.pt",
    device=hub.Device("Samsung Galaxy S23 (Family)"),
    options="--target_runtime onnx",
    input_specs={'image': (1, 3, 224, 224)}
)

compile_job.download_target_model("MobileNet_V2.onnx")
```

---

## Compiling ONNX Models

### ONNX → TensorFlow Lite

```python
import qai_hub as hub

compile_job = hub.submit_compile_job(
    model="mobilenet_v2.onnx",
    device=hub.Device("Samsung Galaxy S23 (Family)")
)
compile_job.download_target_model("MobileNet_V2.tflite")
```

### ONNX → QNN Model Library

```python
compile_job = hub.submit_compile_job(
    model="mobilenet_v2.onnx",
    device=hub.Device("Samsung Galaxy S23 (Family)"),
    options="--target_runtime qnn_lib_aarch64_android"
)
compile_job.download_target_model("MobileNet_V2.so")
```

### ONNX → QNN DLC

```python
compile_job = hub.submit_compile_job(
    model="mobilenet_v2.onnx",
    device=hub.Device("Samsung Galaxy S23 (Family)"),
    options="--target_runtime qnn_dlc"
)
compile_job.download_target_model("MobileNet_V2.dlc")
```

---

## Notes on AIMET Quantized Models

* AIMET‑quantized models (produced by the AI Model Efficiency Toolkit) can be compiled using the same API patterns shown above. The quantized models need to be provided in their supported format (typically PyTorch or ONNX) and can then target the same runtimes.


Below is a unified, detailed document that covers **all example sections** from the Qualcomm® AI Hub Workbench documentation. Each section is summarized with its purpose, key concepts, and important API calls. Citations reference the relevant parts of the source pages.

---

# Qualcomm® AI Hub Workbench – Examples Guide

This guide consolidates the example sections from the AI Hub Workbench documentation. It covers compiling models, profiling, running inference, quantization, linking, devices, job management, frameworks, CLI usage, and deployment.

---

## 1. Compiling Models

### Supported model formats

* **PyTorch**, **ONNX**, **AIMET quantized models**, **TensorFlow via ONNX**.

### Target runtimes

* **TensorFlow Lite (LiteRT)** – good for Android devices.
* **ONNX Runtime** – suited for Windows.
* **Qualcomm® AI Engine Direct (QNN)**:

  * *Context binary* – SoC‑specific.
  * *Model library* – OS‑specific `.so` library (e.g., `aarch64_android`).
  * *DLC* – hardware‑agnostic container.

A specific QNN SDK version can be chosen via `--qairt_version`.

### PyTorch → TFLite workflow

1. Convert model to TorchScript using `torch.jit.trace`.
2. Submit a compile job with `hub.submit_compile_job()`, specifying the device and input shapes.
3. Download the compiled `.tflite` model with `compile_job.download_target_model()`.

You may also compile a saved TorchScript model (e.g., `mobilenet_v2.pt`) directly.

### Other compilation paths

* **PyTorch → QNN model library**: use option `--target_runtime qnn_lib_aarch64_android` to produce a `.so` library.
* **PyTorch → QNN context binary**: `--target_runtime qnn_context_binary` for device‑specific NPU deployment.
* **PyTorch → ONNX**: specify `--target_runtime onnx`.
* **ONNX → TFLite / QNN**: compile ONNX models to TFLite (`.tflite`), QNN model library (`.so`) or QNN DLC (`.dlc`) by choosing the appropriate `--target_runtime`.

---

## 2. Profiling Models

### Purpose

Profiling answers key questions before deployment:

* **Inference latency** on target hardware.
* **Memory usage** relative to a specified budget.
* **NPU utilization**.

### Workflow

1. **Compile the model** (as shown in the previous section) to the desired runtime.
2. **Submit a profile job**: call `hub.submit_profile_job(model=compile_job.get_target_model(), device=hub.Device("…"))`.
3. **Access results**: the returned `ProfileJob` object can download performance statistics.

Profile jobs can specify `--qairt_version` to target a specific AI Runtime version. Profiling is supported only for compiled (optimized) models.

### Profiling a saved TorchScript model

If you have a traced/saved model (`.pt`), compile it first, then profile it. The API functions `upload_model()`, `submit_compile_job()`, and `submit_profile_job()` provide fine‑grained control over options.

---

## 3. Running Inference

### Why run inference jobs?

Running models on target devices can differ from reference implementations (e.g., float32 on CPU vs. float16/int8 on device). Inference jobs let you:

* Upload input data and run the optimized model on real hardware.
* Download output results to compare against a reference implementation.

Only compiled/optimized models can be used for inference jobs.

### Steps to run inference

1. **Compile the model** to the desired runtime.
2. **Prepare input data** as NumPy arrays matching the model’s input specs.
3. **Submit inference job**:

   ```python
   inference_job = hub.submit_inference_job(
       model=compile_job.get_target_model(),
       device=hub.Device("Samsung Galaxy S23 (Family)"),
       inputs={'image': [sample_array]},
   )
   ```
4. The returned `InferenceJob` provides output tensors for evaluation.

You can run inference with various target runtimes (TFLite, QNN `.so`, QNN DLC) by first compiling the model accordingly.

---

## 4. Quantization

### Overview

Quantization converts floating‑point models to fixed‑point (e.g., int8, int16) representations to reduce memory and improve inference speed. Models may see up to a **3× performance improvement** on supported runtimes, with best gains on the Snapdragon® Hexagon processor.

### Calibration

To maintain accuracy, quantized models must be calibrated with unlabeled sample input data to determine scale and zero‑point parameters. Calibration typically uses **500–1000 samples**.

### Workflow

1. **Load and trace the model** to TorchScript.
2. **Compile to ONNX**: call `submit_compile_job()` with `--target_runtime onnx`.
3. **Quantize the ONNX model** using `hub.submit_quantize_job(onnx_model, calibration_data)`, which produces a “fake‑quantization” ONNX graph with `QuantizeLinear/DequantizeLinear` pairs. This is the only ONNX quantization format accepted by the Workbench for subsequent compile jobs.
4. **Compile the quantized model** to the desired runtime (e.g., TFLite or QNN) using the compilation workflows described earlier.

The documentation recommends using the **Imagenette** sample set for calibration when following the tutorial.

---

## 5. Linking

### Purpose

Link jobs combine one or more **QNN DLC models** into a single QNN context binary. They allow multiple graphs to share weights, supporting scenarios like different input shapes for a segmentation network (e.g., portrait vs. landscape).

* **Weight sharing** can be full, partial, or none, depending on the models.
* Link jobs are **exclusive to QNN DLC models**; other formats cannot be linked.

### Example use case

1. Compile two single‑graph DLC models for different input sizes (e.g., 256×256 and 512×512).
2. Link them into a single context binary that can handle both portrait and landscape modes.
3. Deploy the linked context binary to a device; the runtime will route inputs to the correct graph.

---

## 6. Devices

### Listing and filtering devices

* Use `hub.get_devices()` to retrieve a list of available devices.
* Filter devices by name, OS, or attributes:

  ```python
  devices = hub.get_devices(name="Samsung Galaxy S24 (Family)")
  ```
* In the CLI, list devices with:

  ```
  qai-hub list-devices
  ```

### Device object

Each `Device` object provides metadata (name, OS) and is required when submitting compile, profile, or inference jobs. Filtering enables selecting devices with desired hardware capabilities (CPU/GPU/NPU).

---

## 7. Working with Jobs

### Querying jobs

* Retrieve job summaries programmatically using:

  ```python
  job_summaries = hub.get_job_summaries(limit=10)
  ```
* Fetch a specific job by ID (e.g., `"jygdwk7z5"`) with `hub.get_job(job_id)`.

### Accessing job results

For profile jobs, download the profile results:

```python
profile = job.download_profile()
```

### Sharing jobs

Jobs are private by default. Share or revoke access programmatically:

```python
job.modify_sharing(add_emails=['name@company.com'])
job.modify_sharing(delete_emails=['name@company.com'])
```

This allows collaboration while maintaining control over job visibility.

---

## 8. Working with Frameworks

### Framework versions

AI Hub supports multiple versions of the **Qualcomm® AI Engine Direct** framework. To list available frameworks:

```python
frameworks = hub.get_frameworks()
```

CLI equivalent:

```
qai-hub list-frameworks
```

### Special tags

* **default**: the framework version used by default in AI Hub.
* **latest**: the most recently released version.

When submitting jobs (compile, profile, inference), you can specify a framework version using the `framework` parameter to ensure consistent toolchains across model builds.

---

## 9. Command Line Interface

### Overview

The `qai-hub` CLI provides command‑line access to AI Hub Workbench functionality. It can:

* List device information.
* Compile models.
* Profile models.
* Configure client settings.

### Getting help

* View general help:

  ```
  qai-hub --help
  ```
* View command‑specific help:

  ```
  qai-hub submit-profile-job --help
  ```

### Typical workflows

Using the CLI, you can perform many tasks shown in this guide, such as listing devices (`qai-hub list-devices`), submitting compile or profile jobs, and retrieving results. The CLI mirrors the Python API and is useful for scripting or integration into CI pipelines.

---

## 10. Deployment

### Integrating compiled models

After obtaining a deployable asset (TFLite, ONNX, QNN context binary/library/DLC), integrate it into your application by referring to the appropriate runtime documentation:

* [TensorFlow Lite](https://www.tensorflow.org/lite/) for `.tflite` models.
* [ONNX Runtime](https://onnxruntime.ai/) for `.onnx` models.
* [Qualcomm® AI Engine Direct SDK](https://www.qualcomm.com/developer/software/qualcomm-ai-engine-direct-sdk) for QNN binaries.

### Quantized ONNX deployment

Deploying quantized ONNX models involves additional steps for better on‑device performance and reduced memory usage. The Workbench outputs an edge‑centric quantized graph using fake quantization (`Q + DQ`). You can transform this into an **op‑centric quantized representation** (QOp) to reduce model size and create a one‑to‑one mapping between operations and quantized operators.

---

## Conclusion

This consolidated document captures the essential workflows and API usage from all example sections of the Qualcomm® AI Hub Workbench documentation. Use it as a reference when compiling, profiling, quantizing, linking, running inference, managing jobs, selecting devices, choosing framework versions, using the CLI, and deploying optimized models.

