import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const API_URL = 'http://localhost:8000';

function App() {
  const [videoFile, setVideoFile] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [roi, setRoi] = useState({ x: 0, y: 0, w: 0, h: 0 });
  const [isSelecting, setIsSelecting] = useState(false);
  const [selectionStart, setSelectionStart] = useState({ x: 0, y: 0 });
  const [mode, setMode] = useState('translate');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [isPaused, setIsPaused] = useState(true);
  const [selectionMode, setSelectionMode] = useState(false);
  const [orientation, setOrientation] = useState('auto');
  const [rois, setRois] = useState([]);
  const [googleApiKey, setGoogleApiKey] = useState('');
  const [visionResult, setVisionResult] = useState(null);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [autoProposals, setAutoProposals] = useState([]);
  const [selectedProposal, setSelectedProposal] = useState(null);
  const [isSegmenting, setIsSegmenting] = useState(false);
  const [codeTarget, setCodeTarget] = useState('compose');
  const [isPlayingGhost, setIsPlayingGhost] = useState(false);
  const ghostVideoRef = useRef(null);
  const ghostBoxRef = useRef(null);
  const [aiApiKey, setAiApiKey] = useState('');
  const [useAiAnalysis, setUseAiAnalysis] = useState(false);
  const [fluidResult, setFluidResult] = useState(null);
  const [scrubPosition, setScrubPosition] = useState(0);
  const [totalFrames, setTotalFrames] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [controlParams, setControlParams] = useState({
    dampingRatio: 0.7,
    stiffness: 300,
    scaleFactor: 1.0,
    colorTheme: 'purple'
  });
  const [showCodeDrawer, setShowCodeDrawer] = useState(false);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (videoUrl) {
      drawCanvas();
    }
  }, [videoUrl, roi, isSelecting, selectionStart, autoProposals, selectedProposal]);

  useEffect(() => {
    const video = videoRef.current;
    if (video) {
      const handlePlay = () => setIsPaused(false);
      const handlePause = () => {
        setIsPaused(true);
        drawCanvas();
      };

      video.addEventListener('play', handlePlay);
      video.addEventListener('pause', handlePause);

      return () => {
        video.removeEventListener('play', handlePlay);
        video.removeEventListener('pause', handlePause);
      };
    }
  }, [videoUrl]);

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (file && file.type === 'video/mp4') {
      setVideoFile(file);
      setVideoUrl(URL.createObjectURL(file));
      setRoi({ x: 0, y: 0, w: 0, h: 0 });
      setResult(null);
      setError(null);
    }
  };

  const drawCanvas = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    const ctx = canvas.getContext('2d');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Draw auto-segment proposals
    autoProposals.forEach((proposal, index) => {
      ctx.strokeStyle = selectedProposal === index ? '#10b981' : 'rgba(99, 102, 241, 0.4)';
      ctx.lineWidth = 2;
      ctx.strokeRect(proposal.x, proposal.y, proposal.w, proposal.h);

      // Draw index number
      ctx.fillStyle = selectedProposal === index ? '#10b981' : 'rgba(99, 102, 241, 0.8)';
      ctx.font = '14px SF Mono, Monaco, monospace';
      ctx.fillText(`${index + 1}`, proposal.x + 5, proposal.y + 20);
    });

    // Draw ROI selection
    if (roi.w > 0 && roi.h > 0) {
      ctx.strokeStyle = '#a78bfa';
      ctx.lineWidth = 3;
      ctx.strokeRect(roi.x, roi.y, roi.w, roi.h);

      // Add glow effect
      ctx.shadowColor = '#a78bfa';
      ctx.shadowBlur = 10;
      ctx.strokeRect(roi.x, roi.y, roi.w, roi.h);
      ctx.shadowBlur = 0;

      // Draw dimensions with glassmorphism background
      const text = `X: ${roi.x}, Y: ${roi.y}, W: ${roi.w}, H: ${roi.h}`;
      ctx.font = '12px SF Mono, Monaco, monospace';
      const textWidth = ctx.measureText(text).width;
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      ctx.fillRect(roi.x, roi.y - 24, textWidth + 12, 20);
      ctx.fillStyle = '#a78bfa';
      ctx.fillText(text, roi.x + 6, roi.y - 10);
    }

    // Draw current selection
    if (isSelecting) {
      const currentX = selectionStart.currentX || selectionStart.x;
      const currentY = selectionStart.currentY || selectionStart.y;
      const w = currentX - selectionStart.x;
      const h = currentY - selectionStart.y;

      ctx.strokeStyle = '#f472b6';
      ctx.lineWidth = 3;
      ctx.shadowColor = '#f472b6';
      ctx.shadowBlur = 10;
      ctx.strokeRect(selectionStart.x, selectionStart.y, w, h);
      ctx.shadowBlur = 0;
    }
  };

  const handleCanvasMouseDown = (e) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    setSelectionStart({ x, y, currentX: x, currentY: y });
    setIsSelecting(true);
  };

  const handleCanvasMouseMove = (e) => {
    if (!isSelecting) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const currentX = (e.clientX - rect.left) * scaleX;
    const currentY = (e.clientY - rect.top) * scaleY;

    setSelectionStart(prev => ({ ...prev, currentX, currentY }));
    drawCanvas();
  };

  const handleCanvasMouseUp = (e) => {
    if (!isSelecting) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const currentX = (e.clientX - rect.left) * scaleX;
    const currentY = (e.clientY - rect.top) * scaleY;

    const x = Math.min(selectionStart.x, currentX);
    const y = Math.min(selectionStart.y, currentY);
    const w = Math.abs(currentX - selectionStart.x);
    const h = Math.abs(currentY - selectionStart.y);

    const newRoi = { x: Math.round(x), y: Math.round(y), w: Math.round(w), h: Math.round(h) };

    if (mode === 'multi_element') {
      setRois(prev => [...prev, newRoi]);
      setRoi(newRoi); // Also update single ROI for display
      // In multi-element mode, keep selection active to add more elements
    } else {
      setRoi(newRoi);
      setSelectionMode(false); // Exit selection mode after single ROI
    }

    setIsSelecting(false);
  };

  const handleCanvasClick = (e) => {
    if (autoProposals.length === 0) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const clickX = (e.clientX - rect.left) * scaleX;
    const clickY = (e.clientY - rect.top) * scaleY;

    // Check if click is inside any proposal
    for (let i = 0; i < autoProposals.length; i++) {
      const p = autoProposals[i];
      if (clickX >= p.x && clickX <= p.x + p.w &&
          clickY >= p.y && clickY <= p.y + p.h) {
        handleSelectProposal(i);
        return;
      }
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      setSelectionMode(false);
      setAutoProposals([]);
      setSelectedProposal(null);
    }

    // Number keys to select proposals
    if (autoProposals.length > 0 && e.key >= '1' && e.key <= '9') {
      const index = parseInt(e.key) - 1;
      if (index < autoProposals.length) {
        handleSelectProposal(index);
      }
    }
  };

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectionMode, mode, autoProposals]);

  // Handle window resize for canvas coordinate scaling
  useEffect(() => {
    const handleResize = () => {
      if (videoUrl) {
        drawCanvas();
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [videoUrl, roi, isSelecting, selectionStart, autoProposals, selectedProposal]);

  const handleAnalyze = async () => {
    if (!videoFile) {
      setError('Please upload a video');
      return;
    }

    if (mode === 'multi_element') {
      if (rois.length === 0) {
        setError('Please select at least one element');
        return;
      }
    } else if (roi.w === 0 || roi.h === 0) {
      setError('Please select a region of interest');
      return;
    }

    setIsAnalyzing(true);
    setError(null);

    const formData = new FormData();
    formData.append('video', videoFile);
    formData.append('roi', JSON.stringify(roi));
    formData.append('mode', mode);
    formData.append('orientation', orientation);

    if (mode === 'multi_element' && rois.length > 0) {
      formData.append('rois', JSON.stringify(rois));
    }

    try {
      const response = await axios.post(`${API_URL}/api/analyze-motion`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Analysis failed');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleAutoSegment = async () => {
    if (!videoFile) {
      setError('Please upload a video first');
      return;
    }

    setIsSegmenting(true);
    setError(null);
    setAutoProposals([]);
    setSelectedProposal(null);

    const formData = new FormData();
    formData.append('video', videoFile);

    try {
      const response = await axios.post(`${API_URL}/api/auto-segment`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setAutoProposals(response.data.proposals);
      setSelectionMode(true);
      if (response.data.message && response.data.total_detected === 0) {
        setError(response.data.message);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Auto-segmentation failed');
    } finally {
      setIsSegmenting(false);
    }
  };

  const handleFluidAnalyze = async () => {
    if (!videoFile) {
      setError('Please upload a video');
      return;
    }

    if (roi.w === 0 || roi.h === 0) {
      setError('Please select a region of interest');
      return;
    }

    setIsAnalyzing(true);
    setError(null);

    const formData = new FormData();
    formData.append('video', videoFile);
    formData.append('roi', JSON.stringify(roi));

    try {
      const response = await axios.post(`${API_URL}/api/analyze-fluid`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setFluidResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Fluid analysis failed');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleSelectProposal = (index) => {
    const proposal = autoProposals[index];
    setRoi(proposal);
    setSelectedProposal(index);
    setSelectionMode(false);
    setAutoProposals([]);
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 text-white">
      {/* Background gradient orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 -left-20 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 -right-20 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl" />
      </div>

      <div className="relative max-w-7xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
              <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h1 className="text-5xl font-bold bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
              MotionSteal
            </h1>
          </div>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto mb-4">
            Extract animation physics from screen recordings and generate production-ready Jetpack Compose code
          </p>
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 max-w-2xl mx-auto">
            <p className="text-amber-400 text-sm">
              <strong>⚠️ Works best for:</strong> Rigid object translations, simple shape changes, and motion scaling. 
              May struggle with object splitting (sphere → multiple spheres) or non-rigid deformations (sphere → bar).
            </p>
          </div>
        </div>

        {/* Upload Section */}
        <div className="mb-12">
          <div
            className="group relative overflow-hidden rounded-2xl border-2 border-dashed border-gray-700 bg-gray-900/50 backdrop-blur-sm p-12 text-center cursor-pointer transition-all duration-300 hover:border-purple-500/50 hover:bg-gray-800/50"
            onClick={() => fileInputRef.current.click()}
          >
            <div className="absolute inset-0 bg-gradient-to-r from-purple-500/5 to-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept="video/mp4"
              className="hidden"
            />
            <div className="relative">
              <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gray-800 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                <svg className="w-8 h-8 text-gray-400 group-hover:text-purple-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <p className="text-xl font-medium text-gray-200 mb-2">Drop MP4 screen recording here</p>
              <p className="text-gray-500">or click to browse files</p>
            </div>
          </div>
        </div>

        {/* Video and Canvas Section */}
        {videoUrl && (
          <div className="mb-10">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2 text-gray-400 text-sm">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12 a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>
                  {autoProposals.length > 0
                    ? `Found ${autoProposals.length} UI elements - Click a number or box to select`
                    : mode === 'multi_element'
                    ? selectionMode
                      ? `Selection mode active - draw ${rois.length + 1}th element (ESC to finish)`
                      : `Selected ${rois.length} elements - Click to add more`
                    : selectionMode
                    ? 'Selection mode active - drag to select region'
                    : 'Toggle selection mode to draw ROI'}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={handleAutoSegment}
                  disabled={isSegmenting || !videoFile}
                  className="px-4 py-2 rounded-xl text-sm font-medium transition-all duration-300 bg-amber-600 hover:bg-amber-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white"
                >
                  {isSegmenting ? (
                    <>
                      <svg className="animate-spin w-4 h-4 inline mr-2" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Detecting...
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                      Auto-Detect
                    </>
                  )}
                </button>
                <button
                  onClick={() => {
                    setSelectionMode(!selectionMode);
                    setAutoProposals([]);
                    setSelectedProposal(null);
                    if (!selectionMode) {
                      // When enabling selection, pause the video
                      if (videoRef.current) {
                        videoRef.current.pause();
                      }
                    }
                  }}
                  className={`px-4 py-2 rounded-xl text-sm font-medium transition-all duration-300 ${
                    selectionMode
                      ? 'bg-purple-600 hover:bg-purple-500 text-white'
                      : 'bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700'
                  }`}
                >
                  {selectionMode ? (
                    <>
                      <svg className="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                      Exit Selection
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                      </svg>
                      Manual Select
                    </>
                  )}
                </button>
              </div>
            </div>
            <div className="relative rounded-2xl overflow-hidden bg-gray-900/50 backdrop-blur-sm border border-gray-800 shadow-2xl">
              <video
                ref={videoRef}
                src={videoUrl}
                controls
                className="w-full"
                onLoadedMetadata={drawCanvas}
                onSeeked={drawCanvas}
              />
              {selectionMode && (
                <canvas
                  ref={canvasRef}
                  onMouseDown={handleCanvasMouseDown}
                  onMouseMove={handleCanvasMouseMove}
                  onMouseUp={handleCanvasMouseUp}
                  onMouseLeave={() => isSelecting && setIsSelecting(false)}
                  onClick={handleCanvasClick}
                  className="absolute top-0 left-0 w-full h-full cursor-crosshair"
                />
              )}
            </div>
          </div>
        )}

        {/* Scrub Bar */}
        {videoUrl && (
          <div className="mb-10 rounded-2xl bg-gray-900/50 backdrop-blur-sm border border-gray-800 p-6">
            <div className="flex items-center gap-4 mb-4">
              <button
                onClick={() => {
                  if (videoRef.current) {
                    if (isPlaying) {
                      videoRef.current.pause();
                    } else {
                      videoRef.current.play();
                    }
                    setIsPlaying(!isPlaying);
                  }
                }}
                className="w-10 h-10 rounded-full bg-gray-800 hover:bg-gray-700 flex items-center justify-center transition-colors"
              >
                {isPlaying ? (
                  <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                )}
              </button>
              <input
                type="range"
                min="0"
                max="100"
                value={scrubPosition}
                onChange={(e) => {
                  const position = parseFloat(e.target.value);
                  setScrubPosition(position);
                  if (videoRef.current) {
                    videoRef.current.currentTime = (position / 100) * videoRef.current.duration;
                  }
                }}
                className="flex-1 h-2 bg-gray-700 rounded-full appearance-none cursor-pointer"
              />
              <span className="text-sm text-gray-400 font-mono w-20 text-right">
                {scrubPosition.toFixed(0)}%
              </span>
            </div>
          </div>
        )}

        {/* Control Panel */}
        {videoUrl && (
          <div className="mb-10 rounded-2xl bg-gray-900/50 backdrop-blur-sm border border-gray-800 p-6">
            <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4 4m0-4v8m0-6h6a2 2 0 110 4 4h-6" />
              </svg>
              Animation Parameters
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Damping Ratio</label>
                <input
                  type="range"
                  min="0.1"
                  max="1.5"
                  step="0.05"
                  value={controlParams.dampingRatio}
                  onChange={(e) => setControlParams({...controlParams, dampingRatio: parseFloat(e.target.value)})}
                  className="w-full"
                />
                <span className="text-sm text-purple-400 font-mono">{controlParams.dampingRatio.toFixed(2)}</span>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Stiffness</label>
                <input
                  type="range"
                  min="50"
                  max="500"
                  step="10"
                  value={controlParams.stiffness}
                  onChange={(e) => setControlParams({...controlParams, stiffness: parseFloat(e.target.value)})}
                  className="w-full"
                />
                <span className="text-sm text-blue-400 font-mono">{controlParams.stiffness.toFixed(0)}</span>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Scale Factor</label>
                <input
                  type="range"
                  min="0.5"
                  max="2.0"
                  step="0.1"
                  value={controlParams.scaleFactor}
                  onChange={(e) => setControlParams({...controlParams, scaleFactor: parseFloat(e.target.value)})}
                  className="w-full"
                />
                <span className="text-sm text-green-400 font-mono">{controlParams.scaleFactor.toFixed(1)}x</span>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Color Theme</label>
                <select
                  value={controlParams.colorTheme}
                  onChange={(e) => setControlParams({...controlParams, colorTheme: e.target.value})}
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white"
                >
                  <option value="purple">Purple</option>
                  <option value="blue">Blue</option>
                  <option value="green">Green</option>
                  <option value="orange">Orange</option>
                  <option value="pink">Pink</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Controls */}
        {videoUrl && (
          <div className="mb-10 rounded-2xl bg-gray-900/50 backdrop-blur-sm border border-gray-800 p-6">
            <div className="flex flex-wrap gap-6 items-center">
              <div className="flex-1 min-w-[200px]">
                <label className="block text-sm font-medium text-gray-400 mb-2">Analysis Mode</label>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 transition-all"
                >
                  <option value="translate">Physical Motion (Translation/Scale)</option>
                  <option value="fill_progress">Component Fill (Slider/Level)</option>
                  <option value="multi_element">Multi-Element (Stagger & Rotation)</option>
                </select>
              </div>

              {mode === 'fill_progress' && (
                <div className="flex-1 min-w-[200px]">
                  <label className="block text-sm font-medium text-gray-400 mb-2">Orientation</label>
                  <select
                    value={orientation}
                    onChange={(e) => setOrientation(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 transition-all"
                  >
                    <option value="auto">Auto-detect</option>
                    <option value="vertical">Vertical</option>
                    <option value="horizontal">Horizontal</option>
                  </select>
                </div>
              )}

              {mode === 'multi_element' && (
                <div className="flex-1 min-w-[200px]">
                  <label className="block text-sm font-medium text-gray-400 mb-2">Elements Selected</label>
                  <div className="flex items-center gap-3">
                    <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 font-mono text-sm text-purple-400">
                      {rois.length} elements
                    </div>
                    {rois.length > 0 && (
                      <button
                        onClick={() => {
                          setRois([]);
                          setRoi({ x: 0, y: 0, w: 0, h: 0 });
                        }}
                        className="px-3 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 rounded-lg text-sm transition-colors"
                      >
                        Clear All
                      </button>
                    )}
                  </div>
                </div>
              )}

              <div className="flex-1 min-w-[200px]">
                <label className="block text-sm font-medium text-gray-400 mb-2">Selected Region</label>
                <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 font-mono text-sm text-purple-400">
                  X: {roi.x}, Y: {roi.y}, W: {roi.w}, H: {roi.h}
                </div>
              </div>

              <button
                onClick={handleAnalyze}
                disabled={isAnalyzing || roi.w === 0 || roi.h === 0}
                className="px-8 py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:from-gray-700 disabled:to-gray-700 disabled:cursor-not-allowed rounded-xl font-medium transition-all duration-300 shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40 disabled:shadow-none"
              >
                {isAnalyzing ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Analyzing...
                  </span>
                ) : 'Analyze Motion'}
              </button>
              <button
                onClick={handleFluidAnalyze}
                disabled={isAnalyzing || roi.w === 0 || roi.h === 0}
                className="px-8 py-3 bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 disabled:from-gray-700 disabled:to-gray-700 disabled:cursor-not-allowed rounded-xl font-medium transition-all duration-300 shadow-lg shadow-amber-500/25 hover:shadow-amber-500/40 disabled:shadow-none"
              >
                {isAnalyzing ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Analyzing...
                  </span>
                ) : 'Analyze Fluid UI'}
              </button>
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="mb-10 rounded-2xl bg-red-900/20 backdrop-blur-sm border border-red-800/50 p-6">
            <div className="flex items-center gap-3">
              <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-red-300">{error}</p>
            </div>
          </div>
        )}

        {/* Fluid UI Results */}
        {fluidResult && (
          <div className="space-y-8">
            <div className="rounded-2xl bg-gradient-to-r from-amber-900/30 to-orange-900/30 border border-amber-500/30 p-8">
              <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                Fluid UI Analysis
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-6 mb-6">
                <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
                  <p className="text-gray-400 text-sm mb-1">Total Frames</p>
                  <p className="text-xl font-mono text-amber-400">{fluidResult.fluid_metrics.length}</p>
                </div>
                <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
                  <p className="text-gray-400 text-sm mb-1">Phase Transition</p>
                  <p className="text-xl font-mono text-orange-400">
                    {fluidResult.phase_transition ? `${(fluidResult.phase_transition * 1000).toFixed(0)}ms` : 'N/A'}
                  </p>
                </div>
                <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
                  <p className="text-gray-400 text-sm mb-1">Phases Detected</p>
                  <p className="text-xl font-mono text-yellow-400">{fluidResult.phases.length}</p>
                </div>
              </div>
              <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
                <p className="text-gray-400 text-sm mb-3">Animation Phases</p>
                <div className="space-y-2">
                  {fluidResult.phases.map((phase, i) => (
                    <div key={i} className="flex items-center gap-3 text-sm">
                      <span className="w-8 h-8 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center font-mono">
                        {i + 1}
                      </span>
                      <span className="text-gray-300">
                        {phase.name} ({(phase.start_t * 1000).toFixed(0)}ms → {(phase.end_t * 1000).toFixed(0)}ms) - {phase.type}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Code Export */}
            <div className="rounded-2xl bg-gray-900/50 backdrop-blur-sm border border-gray-800 p-8">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center">
                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                  </div>
                  Generated Code
                </h2>
                <div className="flex gap-2">
                  <button
                    onClick={() => copyToClipboard(fluidResult.code?.[codeTarget] || fluidResult.code?.compose || '')}
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
              </div>

              {/* Code Target Tabs */}
              <div className="flex gap-2 mb-4">
                <button
                  onClick={() => setCodeTarget('compose')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    codeTarget === 'compose'
                      ? 'bg-amber-600 text-white'
                      : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  Jetpack Compose
                </button>
                <button
                  onClick={() => setCodeTarget('framer')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    codeTarget === 'framer'
                      ? 'bg-amber-600 text-white'
                      : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  Framer Motion
                </button>
                <button
                  onClick={() => setCodeTarget('flutter')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    codeTarget === 'flutter'
                      ? 'bg-amber-600 text-white'
                      : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  Flutter
                </button>
              </div>

              <pre className="bg-gray-950 rounded-xl p-6 overflow-x-auto text-sm font-mono border border-gray-800">
                <code className="text-gray-300">
                  {fluidResult.code?.[codeTarget] || fluidResult.code?.compose || fluidResult.compose_code}
                </code>
              </pre>
            </div>
          </div>
        )}

        {/* Results Section */}
        {result && (
          <div className="space-y-8">
            {/* Multi-Element Results */}
            {result.total_elements && (
              <div className="rounded-2xl bg-gray-900/50 backdrop-blur-sm border border-gray-800 p-8">
                <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                  </div>
                  Multi-Element Analysis
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-6 mb-6">
                  <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
                    <p className="text-gray-400 text-sm mb-1">Total Elements</p>
                    <p className="text-xl font-mono text-purple-400">{result.total_elements}</p>
                  </div>
                  <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
                    <p className="text-gray-400 text-sm mb-1">Stagger Delays</p>
                    <p className="text-xl font-mono text-blue-400">
                      [{result.stagger_delays.map(d => (d * 1000).toFixed(0)).join(', ')}]ms
                    </p>
                  </div>
                </div>
                <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
                  <p className="text-gray-400 text-sm mb-3">Element Tracks</p>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {Object.entries(result.element_tracks).map(([id, tracks]) => (
                      <div key={id} className="flex items-center gap-3 text-sm">
                        <span className="w-8 h-8 rounded-lg bg-purple-500/20 text-purple-400 flex items-center justify-center font-mono">
                          {id}
                        </span>
                        <span className="text-gray-400">
                          {tracks.length} frames • Delay: {(result.stagger_delays[id] * 1000).toFixed(0)}ms
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Vision Bridge - AI Styling */}
                {result.element_crops && (
                  <div className="mt-8 rounded-xl bg-gradient-to-r from-purple-900/30 to-blue-900/30 border border-purple-500/30 p-6">
                    <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
                      <svg className="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                      AI-Powered Styling (Gemini Vision)
                    </h3>
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-400 mb-2">Google API Key</label>
                        <input
                          type="password"
                          value={googleApiKey}
                          onChange={(e) => setGoogleApiKey(e.target.value)}
                          placeholder="Enter your Google AI API key"
                          className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-purple-500/50"
                        />
                      </div>
                      <div className="flex gap-4">
                        <select
                          value="0"
                          className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white"
                        >
                          {Object.keys(result.element_crops)
                            .filter(k => k.startsWith('start_'))
                            .map((k, i) => (
                              <option key={i} value={k.replace('start_', '')}>
                                Element {k.replace('start_', '')}
                              </option>
                            ))}
                        </select>
                        <button
                          onClick={async () => {
                            if (!googleApiKey) {
                              setError('Please enter your Google API key');
                              return;
                            }
                            setIsSynthesizing(true);
                            try {
                              const elementId = '0';
                              const startCrop = result.element_crops[`start_${elementId}`];
                              const endCrop = result.element_crops[`end_${elementId}`];

                              const startBlob = await fetch(`data:image/png;base64,${startCrop}`).then(r => r.blob());
                              const endBlob = await fetch(`data:image/png;base64,${endCrop}`).then(r => r.blob());

                              const formData = new FormData();
                              formData.append('start_crop', startBlob, 'start.png');
                              formData.append('end_crop', endBlob, 'end.png');
                              formData.append('duration_ms', result.duration_ms || 300);
                              formData.append('max_rotation', 0.0);
                              formData.append('api_key', googleApiKey);

                              const response = await axios.post(`${API_URL}/api/vision-synthesize`, formData, {
                                headers: { 'Content-Type': 'multipart/form-data' },
                              });
                              setVisionResult(response.data);
                            } catch (err) {
                              setError(err.response?.data?.detail || 'Vision synthesis failed');
                            } finally {
                              setIsSynthesizing(false);
                            }
                          }}
                          disabled={isSynthesizing || !googleApiKey}
                          className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:from-gray-700 disabled:to-gray-700 rounded-xl font-medium transition-all"
                        >
                          {isSynthesizing ? 'Generating...' : 'Generate Styled Compose'}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Standard Metrics (for single-element modes) */}
            {!result.total_elements && (
              <div className="rounded-2xl bg-gray-900/50 backdrop-blur-sm border border-gray-800 p-8">
                <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  </div>
                  Analysis Results
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                  <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
                    <p className="text-gray-400 text-sm mb-1">Dominant Axis</p>
                    <p className="text-xl font-mono text-purple-400">{result.dominant_axis}</p>
                  </div>
                  <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
                    <p className="text-gray-400 text-sm mb-1">Duration</p>
                    <p className="text-xl font-mono text-blue-400">{result.duration_ms}ms</p>
                  </div>
                  <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
                    <p className="text-gray-400 text-sm mb-1">Fit Type</p>
                    <p className="text-xl font-mono capitalize text-green-400">{result.fit_type}</p>
                  </div>
                  <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
                    <p className="text-gray-400 text-sm mb-1">Spring MSE</p>
                    <p className="text-xl font-mono text-yellow-400">{result.metrics.spring_mse?.toFixed(6) || 'N/A'}</p>
                  </div>
                </div>

                {result.fit_type === 'spring' && (
                  <div className="mt-6 grid grid-cols-2 gap-6">
                    <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
                      <p className="text-gray-400 text-sm mb-1">Damping Ratio</p>
                      <p className="text-xl font-mono text-purple-400">{result.metrics.damping_ratio.toFixed(3)}</p>
                    </div>
                    <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
                      <p className="text-gray-400 text-sm mb-1">Stiffness</p>
                      <p className="text-xl font-mono text-blue-400">{result.metrics.stiffness.toFixed(1)}</p>
                    </div>
                  </div>
                )}

                {result.fit_type === 'bezier' && (
                  <div className="mt-6 bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
                    <p className="text-gray-400 text-sm mb-1">Bézier Handles</p>
                    <p className="text-xl font-mono text-green-400">
                      [{result.metrics.bezier_handles.map(h => h.toFixed(2)).join(', ')}]
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Ghost-Diff Sandbox */}
            {!result.total_elements && (
              <div className="rounded-2xl bg-gray-900/50 backdrop-blur-sm border border-gray-800 p-8">
                <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  </div>
                  MotionForge Studio - Ghost-Diff Parity
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {/* Left: Original Video */}
                  <div>
                    <p className="text-gray-400 text-sm mb-3">Original Video</p>
                    <div className="relative bg-gray-800 rounded-xl overflow-hidden aspect-video">
                      <video
                        ref={videoRef}
                        src={videoUrl}
                        className="w-full h-full object-cover"
                      />
                      {roi.w > 0 && roi.h > 0 && (
                        <div
                          className="absolute border-2 border-green-500 pointer-events-none"
                          style={{
                            left: `${(roi.x / (videoRef.current?.videoWidth || 1)) * 100}%`,
                            top: `${(roi.y / (videoRef.current?.videoHeight || 1)) * 100}%`,
                            width: `${(roi.w / (videoRef.current?.videoWidth || 1)) * 100}%`,
                            height: `${(roi.h / (videoRef.current?.videoHeight || 1)) * 100}%`,
                          }}
                        />
                      )}
                    </div>
                  </div>

                  {/* Center: Interactive Component */}
                  <div>
                    <p className="text-gray-400 text-sm mb-3">Interactive Component</p>
                    <div className="relative bg-gray-800 rounded-xl overflow-hidden aspect-video flex items-center justify-center">
                      <div
                        ref={ghostBoxRef}
                        className="w-16 h-16 rounded-xl bg-gradient-to-br from-purple-500 to-blue-500 shadow-lg shadow-purple-500/30"
                      />
                    </div>
                  </div>

                  {/* Right: Ghost-Diff Overlay */}
                  <div>
                    <p className="text-gray-400 text-sm mb-3">Ghost-Diff (mix-blend-mode: difference)</p>
                    <div className="relative bg-gray-800 rounded-xl overflow-hidden aspect-video flex items-center justify-center">
                      <div className="absolute inset-0 flex items-center justify-center">
                        <video
                          ref={videoRef}
                          src={videoUrl}
                          className="w-full h-full object-cover"
                          style={{ mixBlendMode: 'difference', opacity: 0.7 }}
                        />
                        <div
                          ref={ghostBoxRef}
                          className="w-16 h-16 rounded-xl bg-gradient-to-br from-purple-500 to-blue-500 shadow-lg shadow-purple-500/30"
                          style={{ mixBlendMode: 'normal', position: 'relative' }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => {
                    if (videoRef.current && ghostBoxRef.current) {
                      // Restart video
                      videoRef.current.currentTime = 0;
                      videoRef.current.play();

                      // Calculate animation parameters
                      const handles = result.metrics.bezier_handles || [0.25, 0.1, 0.25, 1.0];
                      const duration = result.duration_ms;
                      const dominantAxis = result.dominant_axis;

                      // Animate using Web Animations API
                      const keyframes = dominantAxis === 'TranslationX'
                        ? [{ transform: 'translateX(0)' }, { transform: `translateX(200px)` }]
                        : [{ transform: 'translateY(0)' }, { transform: `translateY(200px)` }];

                      const timing = {
                        duration: duration,
                        easing: `cubic-bezier(${handles[0]}, ${handles[1]}, ${handles[2]}, ${handles[3]})`,
                      };

                      ghostBoxRef.current.animate(keyframes, timing).play();
                      setIsPlayingGhost(true);

                      // Stop when video ends
                      videoRef.current.onended = () => {
                        setIsPlayingGhost(false);
                      };
                    }
                  }}
                  disabled={isPlayingGhost}
                  className="mt-4 px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:from-gray-700 disabled:to-gray-700 rounded-xl font-medium transition-all duration-300 shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40 disabled:shadow-none"
                >
                  {isPlayingGhost ? 'Playing...' : 'Run Synchronized Playback'}
                </button>
              </div>
            )}

            {/* Chart - Only for single-element modes */}
            {!result.total_elements && (
              <div className="rounded-2xl bg-gray-900/50 backdrop-blur-sm border border-gray-800 p-8">
                <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
                    </svg>
                  </div>
                  Motion Curve
                </h2>
                <ResponsiveContainer width="100%" height={350}>
                  <LineChart data={result.raw_telemetry}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" strokeOpacity={0.3} />
                    <XAxis dataKey="t" stroke="#6B7280" label={{ value: 'Time (s)', position: 'insideBottom', offset: -5, fill: '#9CA3AF' }} />
                    <YAxis stroke="#6B7280" label={{ value: 'Progress', angle: -90, position: 'insideLeft', fill: '#9CA3AF' }} />
                    <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }} />
                    <Legend />
                    <Line type="monotone" dataKey="progress" stroke="#a78bfa" strokeWidth={3} dot={false} name="Raw Data" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Live Preview - Only for single-element modes */}
            {!result.total_elements && (
              <div className="rounded-2xl bg-gray-900/50 backdrop-blur-sm border border-gray-800 p-8">
                <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  </div>
                  Live Preview
                </h2>
                <div className="flex justify-center items-center h-48 bg-gray-800/50 rounded-xl border border-gray-700/50">
                  <div
                    className="w-16 h-16 rounded-xl bg-gradient-to-br from-purple-500 to-blue-500 shadow-lg shadow-purple-500/30"
                    style={{
                      animation: `motionAnimation ${result.duration_ms}ms ease-in-out infinite alternate`,
                    }}
                  />
                </div>
                <style>{`
                  @keyframes motionAnimation {
                    0% { transform: translateX(0); }
                    100% { transform: translateX(200px); }
                  }
                `}</style>
                <p className="text-gray-400 text-sm mt-4 text-center">
                  Preview using extracted duration ({result.duration_ms}ms)
                </p>
              </div>
            )}

            {/* Code Export */}
            <div className="rounded-2xl bg-gray-900/50 backdrop-blur-sm border border-gray-800 p-8">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                  </div>
                  Generated Code
                </h2>
                <div className="flex gap-2">
                  <button
                    onClick={() => setShowCodeDrawer(!showCodeDrawer)}
                    className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-xl text-sm font-medium transition-all duration-300 border border-gray-700 hover:border-gray-600"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                    </svg>
                    {showCodeDrawer ? 'Close Drawer' : 'Open Drawer'}
                  </button>
                  <button
                    onClick={() => copyToClipboard(result.code?.[codeTarget] || result.code?.compose || '')}
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
              </div>

              {/* Code Drawer */}
              {showCodeDrawer && (
                <div className="fixed inset-y right-0 w-96 bg-gray-900 border-l border-gray-800 shadow-2xl overflow-y-auto z-50">
                  <div className="p-6">
                    <div className="flex justify-between items-center mb-6">
                      <h3 className="text-lg font-bold text-white">Code Export</h3>
                      <button
                        onClick={() => setShowCodeDrawer(false)}
                        className="text-gray-400 hover:text-white"
                      >
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>

                    {/* Quick Actions */}
                    <div className="space-y-3 mb-6">
                      <button
                        onClick={() => window.open('https://codesandbox.io/s/react', '_blank')}
                        className="w-full flex items-center gap-3 px-4 py-3 bg-blue-600 hover:bg-blue-500 rounded-xl text-sm font-medium transition-colors"
                      >
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8-8zm0-14c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6-6z" />
                        </svg>
                        Open in CodeSandbox
                      </button>
                      <button
                        onClick={() => window.open('https://stackblitz.com/edit/react', '_blank')}
                        className="w-full flex items-center gap-3 px-4 py-3 bg-purple-600 hover:bg-purple-500 rounded-xl text-sm font-medium transition-colors"
                      >
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M6 3v12l8-6-6V1H4v6l8 6zM4 13h16" />
                        </svg>
                        Open in StackBlitz
                      </button>
                    </div>

                    {/* Code Tabs */}
                    <div className="flex gap-2 mb-4">
                      <button
                        onClick={() => setCodeTarget('compose')}
                        className={`px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                          codeTarget === 'compose'
                            ? 'bg-purple-600 text-white'
                            : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                        }`}
                      >
                        Compose
                      </button>
                      <button
                        onClick={() => setCodeTarget('framer')}
                        className={`px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                          codeTarget === 'framer'
                            ? 'bg-purple-600 text-white'
                            : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                        }`}
                      >
                        Framer
                      </button>
                      <button
                        onClick={() => setCodeTarget('flutter')}
                        className={`px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                          codeTarget === 'flutter'
                            ? 'bg-purple-600 text-white'
                            : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                        }`}
                      >
                        Flutter
                      </button>
                    </div>

                    {/* Code Display */}
                    <pre className="bg-gray-950 rounded-xl p-4 overflow-x-auto text-xs font-mono border border-gray-800">
                      <code className="text-gray-300">
                        {result.code?.[codeTarget] || result.code?.compose || result.compose_code}
                      </code>
                    </pre>
                  </div>
                </div>
              )}
            </div>

              {/* Code Target Tabs */}
              <div className="flex gap-2 mb-4">
                <button
                  onClick={() => setCodeTarget('compose')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    codeTarget === 'compose'
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  Jetpack Compose
                </button>
                <button
                  onClick={() => setCodeTarget('framer')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    codeTarget === 'framer'
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  Framer Motion
                </button>
                <button
                  onClick={() => setCodeTarget('flutter')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    codeTarget === 'flutter'
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  Flutter
                </button>
              </div>

              <pre className="bg-gray-950 rounded-xl p-6 overflow-x-auto text-sm font-mono border border-gray-800">
                <code className="text-gray-300">
                  {result.code?.[codeTarget] || result.code?.compose || result.compose_code}
                </code>
              </pre>
            </div>

            {/* Vision Synthesis Result */}
            {visionResult && (
              <div className="rounded-2xl bg-gradient-to-r from-purple-900/30 to-blue-900/30 border border-purple-500/30 p-8">
                <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                  </div>
                  AI-Generated Styled Compose
                </h2>
                <div className="flex gap-2 mb-4">
                  <button
                    onClick={() => setCodeTarget('compose')}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      codeTarget === 'compose'
                        ? 'bg-purple-600 text-white'
                        : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                    }`}
                  >
                    Jetpack Compose
                  </button>
                  <button
                    onClick={() => setCodeTarget('framer')}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      codeTarget === 'framer'
                        ? 'bg-purple-600 text-white'
                        : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                    }`}
                  >
                    Framer Motion
                  </button>
                  <button
                    onClick={() => setCodeTarget('flutter')}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      codeTarget === 'flutter'
                        ? 'bg-purple-600 text-white'
                        : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                    }`}
                  >
                    Flutter
                  </button>
                </div>
                <pre className="bg-gray-950 rounded-xl p-6 overflow-x-auto text-sm font-mono border border-gray-800">
                  <code className="text-gray-300">{visionResult.code?.[codeTarget] || visionResult.code?.compose || visionResult.compose_code}</code>
                </pre>
                <button
                  onClick={() => copyToClipboard(visionResult.code?.[codeTarget] || visionResult.code?.compose || visionResult.compose_code)}
                  className="mt-4 flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 rounded-xl text-sm font-medium transition-all"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  Copy Styled Code
                </button>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="mt-20 text-center text-gray-500 text-sm">
          <p>Built with FastAPI, React, and Tailwind CSS</p>
        </div>
      </div>
    </div>
  );
}

export default App;
