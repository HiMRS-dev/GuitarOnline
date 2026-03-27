import { createContext, ReactNode, useContext } from "react";

import type { CurrentUser } from "./types";

const CurrentUserContext = createContext<CurrentUser | null>(null);

type CurrentUserProviderProps = {
  user: CurrentUser | null;
  children: ReactNode;
};

export function CurrentUserProvider({ user, children }: CurrentUserProviderProps) {
  return <CurrentUserContext.Provider value={user}>{children}</CurrentUserContext.Provider>;
}

export function useCurrentUser(): CurrentUser | null {
  return useContext(CurrentUserContext);
}
