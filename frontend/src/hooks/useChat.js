import { useCallback, useReducer, useRef } from "react";
import { sendChatMessage } from "../api/client";

/**
 * useChat hook
 * Manages the full conversation state including SSE streaming,
 * game state updates, and image attachments.
 *
 * Returns: { messages, gameState, isLoading, sendMessage, clearChat }
 */

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
          { id: action.id, role: "user", content: action.content, imagePreview: action.imagePreview },
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

    case "APPEND_TEXT": {
      const msgs = state.messages.map((m) =>
        m.id === action.id ? { ...m, content: m.content + action.text } : m
      );
      return { ...state, messages: msgs };
    }

    case "FINISH_MESSAGE": {
      const msgs = state.messages.map((m) =>
        m.id === action.id ? { ...m, streaming: false } : m
      );
      return { ...state, messages: msgs, isLoading: false };
    }

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

    case "SET_LOADING":
      return { ...state, isLoading: action.value };

    case "CLEAR":
      return initialState;

    default:
      return state;
  }
}

let _idCounter = 0;
const uid = () => `msg_${++_idCounter}_${Date.now()}`;

export function useChat() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortRef = useRef(null);

  const sendMessage = useCallback((text, imageFile) => {
    if (!text.trim() && !imageFile) return;

    // Cancel any in-flight request
    abortRef.current?.abort();

    const userMsgId = uid();
    const imagePreview = imageFile ? URL.createObjectURL(imageFile) : null;

    dispatch({
      type: "ADD_USER_MESSAGE",
      id: userMsgId,
      content: text,
      imagePreview,
    });

    const assistantMsgId = uid();
    dispatch({ type: "START_ASSISTANT_MESSAGE", id: assistantMsgId });

    abortRef.current = sendChatMessage(text, imageFile, {
      onState: (gameState) => {
        dispatch({ type: "SET_GAME_STATE", state: gameState });
      },
      onText: (chunk) => {
        dispatch({ type: "APPEND_TEXT", id: assistantMsgId, text: chunk });
      },
      onDone: () => {
        dispatch({ type: "FINISH_MESSAGE", id: assistantMsgId });
        abortRef.current = null;
      },
      onError: (err) => {
        dispatch({
          type: "ADD_SYSTEM_MESSAGE",
          id: uid(),
          content: `Error: ${err.message}. Please try again.`,
        });
        // Remove the empty assistant bubble
        dispatch({ type: "FINISH_MESSAGE", id: assistantMsgId });
      },
    });
  }, []);

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
