import Chat from "./components/Chat";

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-xl font-semibold text-gray-800">
          📚 Kenniscapture — Chatbot Assistent
        </h1>
        <p className="text-sm text-gray-500">
          Stel vragen over contracten op basis van de vastgelegde kennis
        </p>
      </header>
      <main className="h-[calc(100vh-80px)]">
        <Chat />
      </main>
    </div>
  );
}
