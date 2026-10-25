import { useState } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000';

function App() {
  const [videoFile, setVideoFile] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [framework, setFramework] = useState('Jetpack Compose');
  const [synthesizedCode, setSynthesizedCode] = useState(null);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  const handleFileDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('video/')) {
      setVideoFile(file);
      setVideoUrl(URL.createObjectURL(file));
      setError(null);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setVideoFile(file);
      setVideoUrl(URL.createObjectURL(file));
      setError(null);
    }
  };

  const handleSynthesize = async () => {
    if (!videoFile) {
      setError('Please upload a video');
      return;
    }

    setIsSynthesizing(true);
    setError(null);

    const formData = new FormData();
    formData.append('video', videoFile);
    formData.append('framework', framework);

    try {
      const response = await axios.post(`${API_URL}/api/synthesize`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setSynthesizedCode(response.data.code);
    } catch (err) {
      setError(err.response?.data?.detail || 'Synthesis failed');
    } finally {
      setIsSynthesizing(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-slate-900">
      <div className="container mx-auto px-4 py-12 max-w-5xl">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold mb-4 bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
            MotionForge
          </h1>
          <p className="text-gray-400 text-lg">
            Direct AI-Driven Video-to-Code Synthesis
          </p>
        </div>

        {/* Upload Section */}
        <div className="mb-8 rounded-2xl bg-gray-800/50 backdrop-blur-sm border border-gray-700 p-8">
          <div
            onDrop={handleFileDrop}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-gray-600 rounded-xl p-12 text-center cursor-pointer hover:border-purple-500 transition-colors"
          >
            <input
              type="file"
              accept="video/*"
              onChange={handleFileSelect}
              className="hidden"
              id="video-upload"
            />
            <label htmlFor="video-upload" className="cursor-pointer">
              <svg className="w-16 h-16 mx-auto mb-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <p className="text-gray-300 text-lg mb-2">
                Drop your video here or click to upload
              </p>
              <p className="text-gray-500 text-sm">
                Supports MP4, WebM, MOV
              </p>
            </label>
          </div>

          {videoUrl && (
            <div className="mt-6">
              <video
                src={videoUrl}
                controls
                className="w-full rounded-xl"
              />
            </div>
          )}
        </div>

        {/* Framework Selection */}
        <div className="mb-8 rounded-2xl bg-gray-800/50 backdrop-blur-sm border border-gray-700 p-6">
          <label className="block text-sm font-medium text-gray-400 mb-3">Target Framework</label>
          <div className="flex gap-4">
            {['Jetpack Compose', 'Flutter', 'Framer Motion'].map((fw) => (
              <button
                key={fw}
                onClick={() => setFramework(fw)}
                className={`flex-1 px-6 py-3 rounded-xl font-medium transition-all ${
                  framework === fw
                    ? 'bg-gradient-to-r from-purple-600 to-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                {fw}
              </button>
            ))}
          </div>
        </div>

        {/* Synthesize Button */}
        <div className="mb-8">
          <button
            onClick={handleSynthesize}
            disabled={isSynthesizing || !videoFile}
            className="w-full py-4 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:from-gray-700 disabled:to-gray-700 rounded-xl font-medium transition-all duration-300 shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40 disabled:shadow-none"
          >
            {isSynthesizing ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Synthesizing...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Generate Code
              </span>
            )}
          </button>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-8 rounded-2xl bg-red-900/20 backdrop-blur-sm border border-red-800/50 p-6">
            <div className="flex items-center gap-3">
              <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-red-300">{error}</p>
            </div>
          </div>
        )}

        {/* Code Display */}
        {synthesizedCode && (
          <div className="rounded-2xl bg-gray-900/50 backdrop-blur-sm border border-gray-800 p-8">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4-4M6 16l-4-4 4-4" />
                  </svg>
                </div>
                Generated {framework} Code
              </h2>
              <button
                onClick={() => copyToClipboard(synthesizedCode)}
                className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-xl text-sm font-medium transition-all duration-300 border border-gray-700 hover:border-gray-600"
              >
                {copied ? (
                  <>
                    <svg className="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Copied!
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    Copy to Clipboard
                  </>
                )}
              </button>
            </div>
            <pre className="bg-gray-950 rounded-xl p-6 overflow-x-auto text-sm font-mono border border-gray-800">
              <code className="text-gray-300">{synthesizedCode}</code>
            </pre>
          </div>
        )}

        {/* Footer */}
        <div className="mt-20 text-center text-gray-500 text-sm">
          <p>MotionForge 2.0 - Pure AI-Driven Video-to-Code Synthesis</p>
        </div>
      </div>
    </div>
  );
}

export default App;
