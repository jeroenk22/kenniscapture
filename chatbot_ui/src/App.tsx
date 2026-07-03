import Chat from "./components/Chat";
import ProviderToggle from "./components/ProviderToggle";

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-4">
        <img
          src="/tenbrinke-logo.png"
          alt="Ten Brinke"
          className="h-12 w-12 object-contain shrink-0"
        />
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-gray-800">Kenniscapture — Chatbot Assistent</h1>
          <p className="text-sm text-gray-500">
            Stel vragen over contracten op basis van de vastgelegde kennis
          </p>
        </div>
        <ProviderToggle />
      </header>
      <main className="h-[calc(100vh-80px)]">
        <Chat />
      </main>
    </div>
  );
}
