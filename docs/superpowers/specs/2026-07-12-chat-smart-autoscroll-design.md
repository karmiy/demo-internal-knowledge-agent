# 聊天会话智能跟随底部设计

## 背景与根因

聊天消息区域 `.conversation` 是一个独立的 `overflow-y: auto` 滚动容器。当前 `Chat.tsx` 只在发送问题、显示加载状态和收到回复时更新 React state，没有引用滚动容器、记录用户位置或在 DOM 高度变化后调整 `scrollTop`。因此回复出现在可视区域下方时，用户必须手动滚动才能查看。

## 目标行为

- 初始进入会话时启用自动跟随。
- 当用户距离会话底部不超过 `48px` 时，视为“位于底部”。
- 位于底部时，新增用户消息、加载状态、错误状态、Agent 回复、引用卡片或活动标记后，会话保持在最底部。
- 用户向上滚动并离开底部超过 `48px` 后，暂停自动跟随，不抢夺其历史阅读位置。
- 用户自行滚回距离底部 `48px` 内后，恢复自动跟随；下一次内容变化继续保持底部。
- 使用即时滚动，不使用 smooth animation，避免连续状态更新导致追赶、抖动或动画堆积。

## 实现设计

`Chat` 增加：

- `conversationRef`：指向实际滚动容器；
- `shouldFollowRef`：保存是否跟随底部，初始为 `true`，不使用 state 以避免滚动事件引发额外渲染；
- `isNearBottom(element)`：通过 `scrollHeight - scrollTop - clientHeight <= 48` 判断位置；
- `onScroll`：只根据当前距离更新 `shouldFollowRef`；
- `useLayoutEffect`：在消息、busy 和 error 造成的 DOM 更新完成后，如果 `shouldFollowRef.current` 为真，将 `scrollTop` 设置为 `scrollHeight`。

程序化滚到底部产生的 scroll 事件仍会计算为 near-bottom，因此保持跟随状态。用户离开底部后，DOM 更新不会修改 `scrollTop`。

## 边界与非目标

- 不增加“回到最新消息”悬浮按钮。
- 不改变消息请求、线程、Enter/Shift+Enter 或引用逻辑。
- 不引入滚动库或新依赖。
- 当前回答不是 token streaming；设计仍覆盖 busy 到完整回复的两次高度变化。
- 组件卸载后不保留滚动位置，新会话仍从自动跟随状态开始。

## 测试

前端组件测试通过可控的 `scrollHeight`、`clientHeight` 和 `scrollTop` 模拟真实容器：

1. 初始位于底部时，发送问题、显示 busy 和收到回复均把 `scrollTop` 更新到最新 `scrollHeight`；
2. 用户滚动到离底部超过 `48px` 的位置后，收到回复不会改变 `scrollTop`；
3. 用户滚回阈值内后，下一次内容变化恢复滚动到底部；
4. 恰好 `48px` 时跟随，超过 `48px` 时暂停；
5. 原有键盘发送、输入法和引用测试继续通过。

## 验收标准

- 长会话在用户停留底部时，新回复无需手动滚动即可完整看到。
- 用户向上阅读历史时，新回复不会强制拉回。
- 回到底部后自动跟随恢复。
- 前端测试和生产构建通过。
- Docker 重建后用浏览器验证上述底部跟随与暂停行为。
