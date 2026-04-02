#include <fbxsdk.h>

#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

struct Vec3 {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

struct Tri {
    int a = 0;
    int b = 0;
    int c = 0;
};

struct ObjData {
    std::string name;
    std::string mat_key;
    double r = 0.7;
    double g = 0.7;
    double b = 0.7;
    double a = 1.0;
    std::vector<Vec3> vertices;
    std::vector<Tri> triangles;
};

static bool parse_input(const std::string& path, std::vector<ObjData>& out) {
    std::ifstream in(path);
    if (!in.is_open()) {
        std::cerr << "Failed to open input: " << path << "\n";
        return false;
    }

    std::string tok;
    while (in >> tok) {
        if (tok != "o") {
            std::cerr << "Parse error: expected 'o', got '" << tok << "'\n";
            return false;
        }

        ObjData obj;
        if (!(in >> obj.name)) {
            std::cerr << "Parse error: missing object name\n";
            return false;
        }

        if (!(in >> tok) || tok != "m") {
            std::cerr << "Parse error: expected material token 'm'\n";
            return false;
        }
        if (!(in >> obj.mat_key)) {
            std::cerr << "Parse error: missing material key\n";
            return false;
        }

        if (!(in >> tok) || tok != "c") {
            std::cerr << "Parse error: expected color token 'c'\n";
            return false;
        }
        if (!(in >> obj.r >> obj.g >> obj.b >> obj.a)) {
            std::cerr << "Parse error: invalid color values\n";
            return false;
        }

        int nv = 0;
        if (!(in >> tok) || tok != "v" || !(in >> nv) || nv < 0) {
            std::cerr << "Parse error: invalid vertices header\n";
            return false;
        }
        obj.vertices.reserve(static_cast<size_t>(nv));
        for (int i = 0; i < nv; ++i) {
            Vec3 v;
            if (!(in >> v.x >> v.y >> v.z)) {
                std::cerr << "Parse error: invalid vertex row\n";
                return false;
            }
            obj.vertices.push_back(v);
        }

        int nt = 0;
        if (!(in >> tok) || tok != "f" || !(in >> nt) || nt < 0) {
            std::cerr << "Parse error: invalid faces header\n";
            return false;
        }
        obj.triangles.reserve(static_cast<size_t>(nt));
        for (int i = 0; i < nt; ++i) {
            Tri t;
            if (!(in >> t.a >> t.b >> t.c)) {
                std::cerr << "Parse error: invalid face row\n";
                return false;
            }
            obj.triangles.push_back(t);
        }

        out.push_back(std::move(obj));
    }

    return true;
}

static FbxSurfacePhong* create_material(FbxScene* scene, const ObjData& obj) {
    const std::string mat_name = "MAT_" + obj.mat_key;
    FbxSurfacePhong* mat = FbxSurfacePhong::Create(scene, mat_name.c_str());
    mat->Diffuse.Set(FbxDouble3(obj.r, obj.g, obj.b));
    mat->Ambient.Set(FbxDouble3(obj.r * 0.2, obj.g * 0.2, obj.b * 0.2));
    mat->Emissive.Set(FbxDouble3(0.0, 0.0, 0.0));
    mat->TransparencyFactor.Set(1.0 - obj.a);
    return mat;
}

static FbxMesh* create_mesh(FbxScene* scene, const ObjData& obj) {
    FbxMesh* mesh = FbxMesh::Create(scene, ("MESH_" + obj.name).c_str());
    mesh->InitControlPoints(static_cast<int>(obj.vertices.size()));

    for (int i = 0; i < static_cast<int>(obj.vertices.size()); ++i) {
        const Vec3& v = obj.vertices[static_cast<size_t>(i)];
        mesh->SetControlPointAt(FbxVector4(v.x, v.y, v.z), i);
    }

    for (const Tri& t : obj.triangles) {
        mesh->BeginPolygon();
        mesh->AddPolygon(t.a);
        mesh->AddPolygon(t.b);
        mesh->AddPolygon(t.c);
        mesh->EndPolygon();
    }

    // Explicit normals for better viewer compatibility.
    FbxLayer* layer = mesh->GetLayer(0);
    if (!layer) {
        mesh->CreateLayer();
        layer = mesh->GetLayer(0);
    }

    FbxLayerElementNormal* normals = FbxLayerElementNormal::Create(mesh, "");
    normals->SetMappingMode(FbxLayerElement::eByPolygonVertex);
    normals->SetReferenceMode(FbxLayerElement::eDirect);

    for (const Tri& t : obj.triangles) {
        const Vec3& a = obj.vertices[static_cast<size_t>(t.a)];
        const Vec3& b = obj.vertices[static_cast<size_t>(t.b)];
        const Vec3& c = obj.vertices[static_cast<size_t>(t.c)];

        FbxVector4 u(b.x - a.x, b.y - a.y, b.z - a.z);
        FbxVector4 v(c.x - a.x, c.y - a.y, c.z - a.z);
        FbxVector4 n = u.CrossProduct(v);
        n.Normalize();

        normals->GetDirectArray().Add(FbxVector4(n[0], n[1], n[2]));
        normals->GetDirectArray().Add(FbxVector4(n[0], n[1], n[2]));
        normals->GetDirectArray().Add(FbxVector4(n[0], n[1], n[2]));
    }

    layer->SetNormals(normals);

    return mesh;
}

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr << "Usage: fbxsdk_exporter <input.mesh> <output.fbx>\n";
        return 2;
    }

    std::vector<ObjData> objects;
    if (!parse_input(argv[1], objects)) {
        return 1;
    }
    if (objects.empty()) {
        std::cerr << "No objects to export\n";
        return 1;
    }

    FbxManager* manager = FbxManager::Create();
    if (!manager) {
        std::cerr << "Failed to create FbxManager\n";
        return 1;
    }

    FbxIOSettings* ios = FbxIOSettings::Create(manager, IOSROOT);
    manager->SetIOSettings(ios);

    FbxScene* scene = FbxScene::Create(manager, "Scene");
    FbxNode* root = scene->GetRootNode();
    std::map<std::string, FbxSurfacePhong*> mats;

    for (const ObjData& obj : objects) {
        FbxMesh* mesh = create_mesh(scene, obj);
        FbxNode* node = FbxNode::Create(scene, obj.name.c_str());
        node->SetNodeAttribute(mesh);

        FbxSurfacePhong* mat = nullptr;
        auto it = mats.find(obj.mat_key);
        if (it != mats.end()) {
            mat = it->second;
        } else {
            mat = create_material(scene, obj);
            mats[obj.mat_key] = mat;
        }
        node->AddMaterial(mat);

        root->AddChild(node);
    }

    FbxExporter* exporter = FbxExporter::Create(manager, "");
    const int format = manager->GetIOPluginRegistry()->GetNativeWriterFormat();
    if (!exporter->Initialize(argv[2], format, manager->GetIOSettings())) {
        std::cerr << "Exporter init failed: " << exporter->GetStatus().GetErrorString() << "\n";
        exporter->Destroy();
        manager->Destroy();
        return 1;
    }

    const bool ok = exporter->Export(scene);
    if (!ok) {
        std::cerr << "Export failed: " << exporter->GetStatus().GetErrorString() << "\n";
    }

    exporter->Destroy();
    manager->Destroy();
    return ok ? 0 : 1;
}
