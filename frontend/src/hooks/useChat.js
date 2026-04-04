import { useCallback, useReducer, useRef } from "react";
import { sendChatMessage } from "../api/client";

const DEFAULT_HAND_SETTINGS = [
  { name: "Flush Five",       level: 1, times_played: 0 },
  { name: "Flush House",      level: 1, times_played: 0 },
  { name: "Five of a Kind",   level: 1, times_played: 0 },
  { name: "Straight Flush",   level: 1, times_played: 0 },
  { name: "Four of a Kind",   level: 1, times_played: 0 },
  { name: "Full House",       level: 1, times_played: 0 },
  { name: "Flush",            level: 1, times_played: 0 },
  { name: "Straight",         level: 1, times_played: 0 },
  { name: "Three of a Kind",  level: 1, times_played: 0 },
  { name: "Two Pair",         level: 1, times_played: 0 },
  { name: "Pair",             level: 1, times_played: 0 },
  { name: "High Card",        level: 1, times_played: 0 },
];

const initialState = {
  messages: [],
  gameState: null,
  handSettings: DEFAULT_HAND_SETTINGS,
  isLoading: false,
};

function reducer(state, action) {
  switch (action.type) {
    case "ADD_USER_MESSAGE":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: action.id,
            role: "user",
            content: action.content,
            imagePreviews: action.imagePreviews,
          },
        ],
        isLoading: true,
      };

    case "START_ASSISTANT_MESSAGE":
      return {
        ...state,
        messages: [
          ...state.messages,
          { id: action.id, role: "assistant", content: "", streaming: true },
        ],
      };

    case "APPEND_TEXT":
      return {
        ...state,
        messages: state.messages.map((message) =>
          message.id === action.id
            ? { ...message, content: message.content + action.text }
            : message
        ),
      };

    case "FINISH_MESSAGE":
      return {
        ...state,
        messages: state.messages.map((message) =>
          message.id === action.id ? { ...message, streaming: false } : message
        ),
        isLoading: false,
      };

    case "SET_GAME_STATE": {
      // Merge BE hand structure with user's current level/times_played adjustments.
      // The BE always returns level:1 (CV doesn't detect planet levels), so we
      // preserve the user's current values and only adopt BE ordering/names.
      const backendHands = action.state?.sidebar?.hand_settings ?? [];
      const prevByName = Object.fromEntries(
        (state.handSettings ?? DEFAULT_HAND_SETTINGS).map((h) => [h.name, h])
      );
      const merged = backendHands.map((h) => ({
        name: h.name,
        level: prevByName[h.name]?.level ?? 1,
        times_played: prevByName[h.name]?.times_played ?? 0,
      }));
      return {
        ...state,
        gameState: action.state,
        handSettings: merged.length > 0 ? merged : state.handSettings,
      };
    }

    case "UPDATE_HAND_SETTING":
      return {
        ...state,
        handSettings: (state.handSettings ?? DEFAULT_HAND_SETTINGS).map((hand, i) => {
          if (i !== action.index) return hand;
          const min = action.field === "level" ? 1 : 0;
          const current = hand[action.field] ?? min;
          return { ...hand, [action.field]: Math.max(min, current + action.delta) };
        }),
      };

    case "ADD_SYSTEM_MESSAGE":
      return {
        ...state,
        messages: [
          ...state.messages,
          { id: action.id, role: "system", content: action.content, streaming: false },
        ],
        isLoading: false,
      };

    case "CLEAR":
      return initialState;

    default:
      return state;
  }
}

let idCounter = 0;
const uid = () => `msg_${++idCounter}_${Date.now()}`;

export function useChat() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortRef = useRef(null);

  const buildHistoryPayload = useCallback((messages) => {
    return messages
      .filter((message) => {
        if (message.role !== "user" && message.role !== "assistant") return false;
        if (message.streaming) return false;
        return typeof message.content === "string" && message.content.trim().length > 0;
      })
      .map((message) => ({ role: message.role, content: message.content.trim() }))
      .slice(-12);
  }, []);

  const updateHandSetting = useCallback((index, field, delta) => {
    dispatch({ type: "UPDATE_HAND_SETTING", index, field, delta });
  }, []);

  const sendMessage = useCallback(
    (text, imageFiles = []) => {
      if (!text.trim() && imageFiles.length === 0) return;

      abortRef.current?.abort();

      const userMessageId = uid();
      const imagePreviews = imageFiles.map((file) => URL.createObjectURL(file));

      dispatch({
        type: "ADD_USER_MESSAGE",
        id: userMessageId,
        content: text,
        imagePreviews,
      });

      const assistantMessageId = uid();
      dispatch({ type: "START_ASSISTANT_MESSAGE", id: assistantMessageId });

      const history = buildHistoryPayload(state.messages);

      abortRef.current = sendChatMessage(text, imageFiles, history, state.handSettings, {
        onState: (gameState) => dispatch({ type: "SET_GAME_STATE", state: gameState }),
        onText: (chunk) =>
          dispatch({ type: "APPEND_TEXT", id: assistantMessageId, text: chunk }),
        onDone: () => {
          dispatch({ type: "FINISH_MESSAGE", id: assistantMessageId });
          abortRef.current = null;
        },
        onError: (error) => {
          dispatch({
            type: "ADD_SYSTEM_MESSAGE",
            id: uid(),
            content: `Error: ${error.message}. Please try again.`,
          });
          dispatch({ type: "FINISH_MESSAGE", id: assistantMessageId });
        },
      });
    },
    [buildHistoryPayload, state.messages, state.handSettings]
  );

  const clearChat = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: "CLEAR" });
  }, []);

  return {
    messages: state.messages,
    gameState: state.gameState,
    handSettings: state.handSettings,
    isLoading: state.isLoading,
    sendMessage,
    updateHandSetting,
    clearChat,
  };
}
