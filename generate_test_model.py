import torch
import torchvision
import onnx

def generate_test_model():
    print("Generating MobileNetV2 model...")
    model = torchvision.models.mobilenet_v2(pretrained=True)
    model.eval()

    # Create dummy input
    dummy_input = torch.randn(1, 3, 224, 224)

    # Export to ONNX
    output_path = "mobilenet_v2_test.onnx"
    print(f"Exporting to {output_path}...")
    
    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        export_params=True,        # store the trained parameter weights inside the model file
        opset_version=12,          # the ONNX version to export the model to
        do_constant_folding=True,  # whether to execute constant folding for optimization
        input_names=['image'],     # the model's input names
        output_names=['output'],   # the model's output names
        dynamic_axes={'image': {0: 'batch_size'}, 'output': {0: 'batch_size'}} # variable length axes
    )

    print("Verifying model...")
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)
    print("Model is valid and weights are embedded.")
    return output_path

if __name__ == "__main__":
    generate_test_model()
