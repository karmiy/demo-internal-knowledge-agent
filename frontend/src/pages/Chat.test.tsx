import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { Chat } from "./Chat";

it("renders citations returned by chat", async () => {
  const send = vi.fn().mockResolvedValue({ thread_id: "t1", answer: "使用发布检查单。", activity: ["searched_documents"], citations: [{ evidence_id: "doc:1", document_title: "工程指南", source_locator: "发布流程", snippet: "提交前运行检查单。" }] });
  render(<Chat token="token" sendChat={send} />);
  await userEvent.type(screen.getByLabelText("问题"), "发布流程是什么？");
  await userEvent.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByText("工程指南")).toBeVisible();
  expect(screen.getByText("发布流程", { selector: "span" })).toBeVisible();
});
