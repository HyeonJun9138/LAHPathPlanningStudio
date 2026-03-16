import { useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { getCudaInfo } from './api/client';
import AppLayout from './components/layout/AppLayout';
import { useAppStore } from './stores/appStore';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30_000,
    },
  },
});

function AppBootstrap() {
  const { setCudaInfo, setSelectedDevice } = useAppStore();

  useEffect(() => {
    let cancelled = false;

    async function loadCudaInfo() {
      try {
        const info = await getCudaInfo();
        if (cancelled) {
          return;
        }
        setCudaInfo(info);
        setSelectedDevice(info.available ? info.selected_default || 'cuda:0' : 'cpu');
      } catch {
        if (cancelled) {
          return;
        }
        setCudaInfo({
          available: false,
          selected_default: 'cpu',
          devices: [],
          torch_version: '',
          cuda_version: '',
        });
        setSelectedDevice('cpu');
      }
    }

    void loadCudaInfo();

    return () => {
      cancelled = true;
    };
  }, [setCudaInfo, setSelectedDevice]);

  return <AppLayout />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppBootstrap />
    </QueryClientProvider>
  );
}
