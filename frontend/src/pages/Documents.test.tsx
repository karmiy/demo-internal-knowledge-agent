import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { Documents } from "./Documents";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const documentItem = {
  id: "12345678-abcd",
  title: "工程指南",
  status: "ready",
  error: null,
};

const documentDetail = {
  ...documentItem,
  created_at: "2025-01-02T03:04:05Z",
  updated_at: "2025-01-03T03:04:05Z",
  permissions: [{ subject_type: "department", subject_id: "engineering" }],
  chunk_count: 1,
  chunks: [
    {
      chunk_index: 0,
      section: "发布流程",
      page_number: 2,
      content: "合并主分支前，必须完成测试与代码评审。",
    },
  ],
};

function mockDocumentList() {
  vi.spyOn(api, "documents").mockResolvedValue([documentItem]);
}

it("shows ingestion status returned by the admin API", async () => {
  mockDocumentList();
  render(<Documents token="token" />);
  expect(await screen.findByText("工程指南")).toBeVisible();
  expect(screen.getByText("ready")).toBeVisible();
});

it("opens an accessible preview with permissions and extracted chunks", async () => {
  const user = userEvent.setup();
  mockDocumentList();
  const detailRequest = vi.spyOn(api, "document").mockResolvedValue(documentDetail);

  render(<Documents token="token" />);
  const openButton = await screen.findByRole("button", { name: /工程指南/ });
  await user.click(openButton);

  expect(detailRequest).toHaveBeenCalledWith("token", "12345678-abcd");
  const dialog = await screen.findByRole("dialog", { name: "工程指南" });
  expect(dialog).toHaveAttribute("aria-modal", "true");
  expect(screen.getByText("department: engineering")).toBeVisible();
  expect(screen.getByText("发布流程")).toBeVisible();
  expect(screen.getByText("合并主分支前，必须完成测试与代码评审。")).toBeVisible();

  const closeButton = screen.getByRole("button", { name: "关闭文档预览" });
  expect(closeButton).toHaveFocus();
  await user.click(closeButton);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(openButton).toHaveFocus();
});

it("shows a loading state while the preview request is pending", async () => {
  const user = userEvent.setup();
  mockDocumentList();
  vi.spyOn(api, "document").mockReturnValue(new Promise(() => {}));

  render(<Documents token="token" />);
  await user.click(await screen.findByRole("button", { name: /工程指南/ }));

  expect(screen.getByRole("dialog", { name: "工程指南" })).toBeVisible();
  expect(screen.getByText("正在读取提取内容…")).toBeVisible();
});

it("shows a detail request error and closes with Escape", async () => {
  const user = userEvent.setup();
  mockDocumentList();
  vi.spyOn(api, "document").mockRejectedValue(new Error("无法读取文档"));

  render(<Documents token="token" />);
  await user.click(await screen.findByRole("button", { name: /工程指南/ }));

  expect(await screen.findByRole("alert")).toHaveTextContent("无法读取文档");
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("shows an empty state when no extracted chunks are available", async () => {
  const user = userEvent.setup();
  mockDocumentList();
  vi.spyOn(api, "document").mockResolvedValue({
    ...documentDetail,
    chunk_count: 0,
    chunks: [],
  });

  render(<Documents token="token" />);
  await user.click(await screen.findByRole("button", { name: /工程指南/ }));

  expect(await screen.findByText("暂无可预览的提取内容。")).toBeVisible();
});
