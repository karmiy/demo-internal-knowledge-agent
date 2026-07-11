import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((complete) => {
    resolve = complete;
  });
  return { promise, resolve };
}

function setScrollMetrics(
  element: HTMLElement,
  { scrollHeight, clientHeight, scrollTop }: { scrollHeight: number; clientHeight: number; scrollTop: number },
) {
  Object.defineProperties(element, {
    scrollHeight: { configurable: true, value: scrollHeight },
    clientHeight: { configurable: true, value: clientHeight },
    scrollTop: { configurable: true, writable: true, value: scrollTop },
  });
}

function getConversation(container: HTMLElement) {
  const conversation = container.querySelector<HTMLElement>(".conversation");
  if (!conversation) throw new Error("Conversation container not found");
  return conversation;
}

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

it("renders only Agent messages as Markdown", async () => {
  const send = vi.fn().mockResolvedValue({
    ...chatResult,
    answer: "**Agent 重点**",
  });
  const { container } = render(<Chat token="token" sendChat={send} />);

  fireEvent.change(screen.getByRole("textbox", { name: "问题" }), {
    target: { value: "**用户原文**" },
  });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));

  expect(await screen.findByText("Agent 重点")).toHaveProperty("tagName", "STRONG");
  expect(screen.getByText("**用户原文**")).toBeVisible();
  expect(container.querySelector(".message.user strong")).not.toBeInTheDocument();
});

it("follows new assistant content when the conversation is at the bottom", async () => {
  const pending = deferred<typeof chatResult>();
  const send = vi.fn().mockReturnValue(pending.promise);
  const { container } = render(<Chat token="token" sendChat={send} />);
  const conversation = getConversation(container);
  setScrollMetrics(conversation, { scrollHeight: 1000, clientHeight: 400, scrollTop: 600 });
  fireEvent.scroll(conversation);

  fireEvent.change(screen.getByRole("textbox", { name: "问题" }), { target: { value: "发布流程是什么？" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await screen.findByRole("status");

  setScrollMetrics(conversation, { scrollHeight: 1400, clientHeight: 400, scrollTop: 1000 });
  await act(async () => pending.resolve(chatResult));

  await screen.findByText(chatResult.answer);
  expect(conversation.scrollTop).toBe(1400);
});

it("keeps following while the busy indicator adds content", async () => {
  const pending = deferred<typeof chatResult>();
  const { container } = render(<Chat token="token" sendChat={vi.fn().mockReturnValue(pending.promise)} />);
  const conversation = getConversation(container);
  setScrollMetrics(conversation, { scrollHeight: 1000, clientHeight: 400, scrollTop: 600 });
  fireEvent.scroll(conversation);
  Object.defineProperty(conversation, "scrollHeight", { configurable: true, value: 1200 });

  fireEvent.change(screen.getByRole("textbox", { name: "问题" }), { target: { value: "发布流程是什么？" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));

  await waitFor(() => expect(conversation.scrollTop).toBe(1200));
  await act(async () => pending.resolve(chatResult));
});

it("does not move when the user is 49 pixels away from the bottom", async () => {
  const pending = deferred<typeof chatResult>();
  const { container } = render(<Chat token="token" sendChat={vi.fn().mockReturnValue(pending.promise)} />);
  const conversation = getConversation(container);

  fireEvent.change(screen.getByRole("textbox", { name: "问题" }), { target: { value: "发布流程是什么？" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await screen.findByRole("status");

  setScrollMetrics(conversation, { scrollHeight: 1000, clientHeight: 400, scrollTop: 551 });
  fireEvent.scroll(conversation);
  Object.defineProperty(conversation, "scrollHeight", { configurable: true, value: 1400 });
  await act(async () => pending.resolve(chatResult));

  await screen.findByText(chatResult.answer);
  expect(conversation.scrollTop).toBe(551);
});

it("resumes following when the user returns to 48 pixels from the bottom", async () => {
  const pending = deferred<typeof chatResult>();
  const { container } = render(<Chat token="token" sendChat={vi.fn().mockReturnValue(pending.promise)} />);
  const conversation = getConversation(container);

  fireEvent.change(screen.getByRole("textbox", { name: "问题" }), { target: { value: "发布流程是什么？" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await screen.findByRole("status");

  setScrollMetrics(conversation, { scrollHeight: 1000, clientHeight: 400, scrollTop: 551 });
  fireEvent.scroll(conversation);
  Object.defineProperty(conversation, "scrollTop", { configurable: true, writable: true, value: 552 });
  fireEvent.scroll(conversation);
  Object.defineProperty(conversation, "scrollHeight", { configurable: true, value: 1400 });
  await act(async () => pending.resolve(chatResult));

  await screen.findByText(chatResult.answer);
  expect(conversation.scrollTop).toBe(1400);
});
