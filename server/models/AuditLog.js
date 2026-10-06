const mongoose = require('mongoose');

const auditLogSchema = new mongoose.Schema(
  {
    paymentId: { type: String, required: true, index: true },
    userId: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true, index: true },
    timestamp: { type: Date, default: Date.now, index: true },
    mlProbability: Number,
    recoveryScore: Number,
    recommendedAction: String,
    finalAction: String,
    reasoning: String,
    confidence: Number,
    source: { type: String, enum: ['llm', 'fallback', 'merchant'] },
    ruleOverride: { type: Boolean, default: false },
    status: {
      type: String,
      enum: ['recommended', 'executed', 'overridden', 'rejected'],
      required: true,
    },
  },
  { timestamps: false }
);

module.exports = mongoose.model('AuditLog', auditLogSchema);