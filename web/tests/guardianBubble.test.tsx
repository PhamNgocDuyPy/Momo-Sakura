import { fireEvent, render, screen } from "@testing-library/react";
import { GuardianProvider, initialGuardianState } from "../src/state/guardianStore";
import GuardianBubble from "../src/components/guardian/GuardianBubble";
import ScanPopup from "../src/components/guardian/ScanPopup";
import { snapToEdge } from "../src/lib/bubblePosition";

function renderGuardian(status: "idle" | "stage1" = "idle") {
  render(
    <GuardianProvider
      initialState={{
        ...initialGuardianState,
        popup: { ...initialGuardianState.popup, status },
      }}
    >
      <GuardianBubble />
      <ScanPopup />
    </GuardianProvider>,
  );
}

describe("snapToEdge", () => {
  it("snaps to the nearest side and clamps y", () => {
    const vp = { width: 400, height: 800 };
    expect(snapToEdge({ x: 100, y: 900 }, vp)).toEqual({ x: 0, y: 744 });
    expect(snapToEdge({ x: 300, y: -20 }, vp)).toEqual({ x: 344, y: 0 });
  });
});

describe("Guardian bubble and popup", () => {
  it("opens the popup synchronously on tap and hides the bubble", () => {
    renderGuardian();
    const bubble = screen.getByTestId("guardian-bubble");
    fireEvent.pointerDown(bubble, { clientX: 10, clientY: 10 });
    fireEvent.pointerUp(bubble, { clientX: 12, clientY: 11 });
    expect(screen.getByTestId("scan-popup")).toBeInTheDocument();
    expect(screen.queryByTestId("guardian-bubble")).toBeNull();
    expect(screen.getByLabelText(/Dán nội dung/)).toBeInTheDocument();
    expect(screen.getByLabelText(/gõ lệnh/)).toBeInTheDocument();
    expect(screen.getByText("Quét QR")).toBeInTheDocument();
    expect(screen.getByLabelText(/Cho phép lưu bằng chứng/)).not.toBeChecked();
    expect(screen.getByLabelText(/Kiểm tra clipboard/)).not.toBeChecked();
  });

  it("does not open when the pointer moved past the drag threshold", () => {
    renderGuardian();
    const bubble = screen.getByTestId("guardian-bubble");
    fireEvent.pointerDown(bubble, { clientX: 0, clientY: 0 });
    fireEvent.pointerUp(bubble, { clientX: 40, clientY: 0 });
    expect(screen.queryByTestId("scan-popup")).toBeNull();
  });

  it("shows the scan animation while processing", () => {
    render(
      <GuardianProvider
        initialState={{
          ...initialGuardianState,
          popup: { ...initialGuardianState.popup, open: true, status: "stage1" },
        }}
      >
        <ScanPopup />
      </GuardianProvider>,
    );
    expect(screen.getByTestId("scan-animation")).toBeInTheDocument();
  });
});
