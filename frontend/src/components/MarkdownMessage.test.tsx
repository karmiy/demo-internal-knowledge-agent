import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { MarkdownMessage } from "./MarkdownMessage";

afterEach(cleanup);

it("renders Agent Markdown as semantic HTML", () => {
  const { container } = render(
    <MarkdownMessage
      content={"**重点**\n\n1. 第一步\n2. 第二步\n\n---\n\n| 项目 | 结果 |\n| --- | --- |\n| CI | 通过 |"}
    />,
  );

  expect(screen.getByText("重点").tagName).toBe("STRONG");
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
  expect(container.querySelector("hr")).toBeInTheDocument();
  expect(screen.getByRole("table")).toBeVisible();
});

it("does not turn raw HTML into live elements", () => {
  render(<MarkdownMessage content={'<button onclick="alert(1)">危险</button>'} />);

  expect(screen.queryByRole("button", { name: "危险" })).not.toBeInTheDocument();
});

it("opens safe links in a separate tab", () => {
  render(<MarkdownMessage content="[内部文档](https://example.com/docs)" />);

  expect(screen.getByRole("link", { name: "内部文档" })).toHaveAttribute("target", "_blank");
  expect(screen.getByRole("link", { name: "内部文档" })).toHaveAttribute("rel", "noreferrer noopener");
});

it("does not make unsafe link protocols actionable", () => {
  render(<MarkdownMessage content="[危险链接](javascript:alert(1))" />);

  expect(screen.getByText("危险链接").closest("a")).toHaveAttribute("href", "");
  expect(screen.queryByRole("link", { name: "危险链接" })).not.toBeInTheDocument();
});
