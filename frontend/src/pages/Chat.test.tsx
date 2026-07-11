import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { Chat } from "./Chat";

afterEach(cleanup);

const chatResult = {
  thread_id: "t1",
  answer: "使用发布检查单。",
  activity: ["searched_documents" as const],
  citations: [],
};

it("exposes an accessible question name without a visible label", () => {
  render(<Chat token="token" />);

  expect(screen.queryByText("问题")).not.toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "问题" })).toBeVisible();
});

it("sends the question when Enter is pressed", async () => {
  const user = userEvent.setup();
  const send = vi.fn().mockResolvedValue(chatResult);
  render(<Chat token="token" sendChat={send} />);

  const question = screen.getByRole("textbox", { name: "问题" });
  await user.type(question, "发布流程是什么？");
  await user.keyboard("{Enter}");

  expect(send).toHaveBeenCalledTimes(1);
  expect(send).toHaveBeenCalledWith("token", "发布流程是什么？", undefined);
});

it("adds a newline without sending when Shift+Enter is pressed", async () => {
  const user = userEvent.setup();
  const send = vi.fn().mockResolvedValue(chatResult);
  render(<Chat token="token" sendChat={send} />);

  const question = screen.getByRole("textbox", { name: "问题" });
  await user.type(question, "第一行");
  await user.keyboard("{Shift>}{Enter}{/Shift}");

  expect(question).toHaveValue("第一行\n");
  expect(send).not.toHaveBeenCalled();
});

it("does not send when Enter is pressed during composition", () => {
  const send = vi.fn().mockResolvedValue(chatResult);
  render(<Chat token="token" sendChat={send} />);

  const question = screen.getByRole("textbox", { name: "问题" });
  fireEvent.change(question, { target: { value: "发布流程" } });
  fireEvent.keyDown(question, { key: "Enter", isComposing: true });

  expect(send).not.toHaveBeenCalled();
});

it("renders citations returned by chat", async () => {
  const send = vi.fn().mockResolvedValue({ thread_id: "t1", answer: "使用发布检查单。", activity: ["searched_documents"], citations: [{ evidence_id: "doc:1", document_title: "工程指南", source_locator: "发布流程", snippet: "提交前运行检查单。" }] });
  render(<Chat token="token" sendChat={send} />);
  await userEvent.type(screen.getByLabelText("问题"), "发布流程是什么？");
  await userEvent.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByText("工程指南")).toBeVisible();
  expect(screen.getByText("发布流程", { selector: "span" })).toBeVisible();
});
