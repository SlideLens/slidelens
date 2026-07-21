import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Finding } from "@/api/schemas";
import { SlideViewer } from "./SlideViewer";

const baseFinding: Finding = {
  id: "f1",
  slide_num: 1,
  category: "TYPOGRAPHY",
  severity: "MAJOR",
  title: "Мелкий шрифт",
  description: "d",
  fix_suggestion: "f",
  bbox: { x: 0.1, y: 0.1, w: 0.2, h: 0.2 },
  auto_fixable: false,
  auto_fixed: false,
  source: "slide_analyzer",
};

describe("SlideViewer", () => {
  it("renders the real screenshot when a finding has one", () => {
    render(
      <SlideViewer
        slideNum={1}
        findings={[{ ...baseFinding, screenshot_url: "/api/v1/files/abc?sig=xyz" }]}
        onFrameClick={vi.fn()}
      />,
    );
    const img = screen.getByAltText("Слайд 1");
    expect(img).toHaveAttribute("src", "/api/v1/files/abc?sig=xyz");
  });

  it("falls back to the placeholder when no finding has a screenshot", () => {
    render(<SlideViewer slideNum={1} findings={[baseFinding]} onFrameClick={vi.fn()} />);
    expect(screen.queryByAltText("Слайд 1")).not.toBeInTheDocument();
  });

  it("clicking a bbox frame still scrolls to the matching finding", async () => {
    const onFrameClick = vi.fn();
    render(
      <SlideViewer
        slideNum={1}
        findings={[{ ...baseFinding, screenshot_url: "/api/v1/files/abc?sig=xyz" }]}
        onFrameClick={onFrameClick}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByTitle("Мелкий шрифт"));
    expect(onFrameClick).toHaveBeenCalledWith("f1");
  });

  it("makes the whole bbox area the hit target, not just the pin", async () => {
    const onFrameClick = vi.fn();
    render(<SlideViewer slideNum={1} findings={[baseFinding]} onFrameClick={onFrameClick} />);

    const region = screen.getByTitle("Мелкий шрифт");
    expect(region.style.width).toBe("20%");
    expect(region.style.height).toBe("20%");
    await userEvent.setup().click(region);
    expect(onFrameClick).toHaveBeenCalledWith("f1");
  });

  it("keeps a pin anchored at 0,0 fully inside the (clipped) slide box", () => {
    render(
      <SlideViewer
        slideNum={1}
        findings={[{ ...baseFinding, bbox: { x: 0, y: 0, w: 0.2, h: 0.2 } }]}
        onFrameClick={vi.fn()}
        numberOf={() => 3}
      />,
    );

    const pin = screen.getByText("3");
    // Смещение только положительное — половина пина больше не уезжает за край.
    expect(pin.style.transform).toBe("translate(3px, 3px)");
  });

  it("offsets pins whose bboxes share a corner instead of stacking them", () => {
    render(
      <SlideViewer
        slideNum={1}
        findings={[
          { ...baseFinding, id: "a", bbox: { x: 0.1, y: 0.1, w: 0.2, h: 0.2 } },
          { ...baseFinding, id: "b", title: "Второй", bbox: { x: 0.1, y: 0.1, w: 0.3, h: 0.3 } },
        ]}
        onFrameClick={vi.fn()}
        numberOf={(id) => (id === "a" ? 1 : 2)}
      />,
    );

    expect(screen.getByText("1").style.transform).toBe("translate(3px, 3px)");
    expect(screen.getByText("2").style.transform).toBe("translate(3px, 29px)");
  });

  it("moves a whole-slide bbox into the «весь слайд» strip instead of framing it", async () => {
    const onFrameClick = vi.fn();
    render(
      <SlideViewer
        slideNum={1}
        findings={[{ ...baseFinding, bbox: { x: 0, y: 0, w: 1, h: 1 } }]}
        onFrameClick={onFrameClick}
        numberOf={() => 4}
      />,
    );

    expect(screen.getByText("весь слайд")).toBeInTheDocument();
    const chip = screen.getByTitle("Мелкий шрифт");
    // Не рамка на весь слайд, а компактный чип.
    expect(chip.style.width).toBe("");
    await userEvent.setup().click(chip);
    expect(onFrameClick).toHaveBeenCalledWith("f1");
  });

  it("prefers the raw slide render and draws its own frame over it", () => {
    render(
      <SlideViewer
        slideNum={1}
        findings={[{ ...baseFinding, screenshot_url: "/api/v1/files/annotated?sig=x" }]}
        onFrameClick={vi.fn()}
        slideUrl="/api/v1/files/raw?sig=y"
      />,
    );

    expect(screen.getByAltText("Слайд 1")).toHaveAttribute("src", "/api/v1/files/raw?sig=y");
    // Уголки рамки рисуем сами — их видно в разметке мишени.
    expect(screen.getByTitle("Мелкий шрифт").querySelectorAll("i")).toHaveLength(4);
  });

  it("draws no frame of its own when falling back to the server-annotated image", () => {
    render(
      <SlideViewer
        slideNum={1}
        findings={[{ ...baseFinding, screenshot_url: "/api/v1/files/annotated?sig=x" }]}
        onFrameClick={vi.fn()}
      />,
    );

    expect(screen.getByAltText("Слайд 1")).toHaveAttribute("src", "/api/v1/files/annotated?sig=x");
    // Рамка уже впечатана в PNG — второй контур поверх неё был бы дублем.
    expect(screen.getByTitle("Мелкий шрифт").querySelectorAll("i")).toHaveLength(0);
  });

  it("stacks a small bbox above a large one so it stays clickable", () => {
    render(
      <SlideViewer
        slideNum={1}
        findings={[
          { ...baseFinding, id: "big", title: "Большая", bbox: { x: 0, y: 0, w: 0.7, h: 0.7 } },
          { ...baseFinding, id: "small", title: "Мелкая", bbox: { x: 0.1, y: 0.1, w: 0.1, h: 0.1 } },
        ]}
        onFrameClick={vi.fn()}
      />,
    );

    const big = Number(screen.getByTitle("Большая").style.zIndex);
    const small = Number(screen.getByTitle("Мелкая").style.zIndex);
    expect(small).toBeGreaterThan(big);
  });
});
