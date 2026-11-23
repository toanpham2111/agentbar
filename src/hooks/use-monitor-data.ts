import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { monitorApi } from "../lib/api";

export function useProviders() {
  return useQuery({ queryKey: ["providers"], queryFn: monitorApi.getProviders });
}

export function useUsageSummary() {
  return useQuery({ queryKey: ["usage-summary"], queryFn: monitorApi.getUsageSummary });
}

export function useRefreshAll() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: monitorApi.refreshAll,
    onSuccess: (providers) => {
      queryClient.setQueryData(["providers"], providers);
      void queryClient.invalidateQueries({ queryKey: ["usage-summary"] });
      void queryClient.invalidateQueries({ queryKey: ["usage-history"] });
    },
  });
}

export function useRefreshProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: monitorApi.refreshProvider,
    onSuccess: (provider) => {
      queryClient.setQueryData(["providers"], (current: typeof provider[] | undefined) =>
        current?.map((item) => item.providerId === provider.providerId ? provider : item) ?? [provider],
      );
      void queryClient.invalidateQueries({ queryKey: ["usage-summary"] });
    },
  });
}
