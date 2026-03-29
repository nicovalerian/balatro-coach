import { useCallback, useReducer, useRef } from "react";
import { sendChatMessage } from "../api/client";

const initialState = {
  messages: [],
  gameState: null,
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

    case "SET_GAME_STATE":
      return { ...state, gameState: action.state };

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

      abortRef.current = sendChatMessage(text, imageFiles, history, {
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
    [buildHistoryPayload, state.messages]
  );

  const clearChat = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: "CLEAR" });
  }, []);

  return {
    messages: state.messages,
    gameState: state.gameState,
    isLoading: state.isLoading,
    sendMessage,
    clearChat,
  };
}
