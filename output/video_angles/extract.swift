import Foundation
import AVFoundation
import AppKit
let args = CommandLine.arguments
let asset = AVURLAsset(url: URL(fileURLWithPath: args[1]))
let generator = AVAssetImageGenerator(asset: asset)
generator.appliesPreferredTrackTransform = true
generator.requestedTimeToleranceBefore = .zero
generator.requestedTimeToleranceAfter = .zero
let t = CMTime(seconds: Double(args[2])!, preferredTimescale: 600)
let img = try generator.copyCGImage(at: t, actualTime: nil)
let bitmap = NSBitmapImageRep(cgImage: img)
try bitmap.representation(using: .jpeg, properties: [.compressionFactor: 0.95])!.write(to: URL(fileURLWithPath: args[3]))
