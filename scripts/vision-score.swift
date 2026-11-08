// On-device ranking hints, not an authority on artistic merit or family identity.
import Foundation
import Vision
import ImageIO

while let line = readLine() {
    autoreleasepool {
        var identity = "unknown"
        do {
            let input = try JSONSerialization.jsonObject(with: Data(line.utf8)) as! [String:String]
            identity = input["id"]!
            let url = URL(fileURLWithPath: input["path"]!)
            let handler = VNImageRequestHandler(url:url, options:[:])
            let aesthetic = VNCalculateImageAestheticsScoresRequest()
            let faces = VNDetectFaceCaptureQualityRequest()
            let classification = VNClassifyImageRequest()
            try handler.perform([aesthetic,faces,classification])
            let score = aesthetic.results?.first
            let faceResults = faces.results ?? []
            let labels = (classification.results ?? []).prefix(12).map { ["label":$0.identifier,"confidence":$0.confidence] as [String:Any] }
            let result: [String:Any] = ["id":identity,"aesthetic":score?.overallScore ?? 0,"utility":score?.isUtility ?? false,"faces":faceResults.count,"faceQuality":faceResults.map { $0.faceCaptureQuality ?? 0 },"labels":labels]
            let data = try JSONSerialization.data(withJSONObject:result,options:[.sortedKeys])
            print(String(data:data,encoding:.utf8)!);fflush(stdout)
        } catch {
            let result = ["id":identity,"error":String(describing:error)]
            let data = try! JSONSerialization.data(withJSONObject:result)
            print(String(data:data,encoding:.utf8)!);fflush(stdout)
        }
    }
}
