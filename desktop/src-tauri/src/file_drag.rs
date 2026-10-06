//! Shell file drag, COPY only. Never launch, move or delete the source file.
#[cfg(windows)]
fn data_object(path:&str) -> windows::core::Result<windows::Win32::System::Com::IDataObject> {
    use windows::{core::PCWSTR,Win32::{System::Com::IBindCtx,UI::Shell::{IShellItem,SHCreateItemFromParsingName,BHID_DataObject}}};
    let wide:Vec<u16>=path.encode_utf16().chain(Some(0)).collect();
    unsafe {
        let item:IShellItem=SHCreateItemFromParsingName(PCWSTR(wide.as_ptr()),None::<&IBindCtx>)?;
        item.BindToHandler(None::<&IBindCtx>,&BHID_DataObject)
    }
}

#[cfg(windows)]
pub fn start(path: &str) -> Result<bool, String> {
    use windows::{core::{implement, BOOL, HRESULT}, Win32::{
        System::{Ole::{IDropSource, IDropSource_Impl, DoDragDrop,
            OleInitialize, OleUninitialize, DROPEFFECT, DROPEFFECT_COPY}, SystemServices::{MODIFIERKEYS_FLAGS, MK_LBUTTON}},
        Foundation::{DRAGDROP_S_CANCEL, DRAGDROP_S_DROP, DRAGDROP_S_USEDEFAULTCURSORS}}};
    #[implement(IDropSource)]
    struct Source;
    impl IDropSource_Impl for Source_Impl {
        fn QueryContinueDrag(&self, escape: BOOL, keys: MODIFIERKEYS_FLAGS) -> HRESULT {
            if escape.as_bool() { DRAGDROP_S_CANCEL }
            else if keys.0 & MK_LBUTTON.0 == 0 { DRAGDROP_S_DROP }
            else { HRESULT(0) }
        }
        fn GiveFeedback(&self, _: DROPEFFECT) -> HRESULT { DRAGDROP_S_USEDEFAULTCURSORS }
    }
    struct OleGuard;
    impl Drop for OleGuard { fn drop(&mut self) { unsafe { OleUninitialize() } } }
    unsafe {
        OleInitialize(None).map_err(|_| "Windows no pudo iniciar el arrastre".to_string())?;
        let _guard=OleGuard;
        let data=data_object(path)
            .map_err(|_| "Windows no pudo preparar el archivo".to_string())?;
        let source:IDropSource=Source.into();
        let mut effect=DROPEFFECT::default();
        let result=DoDragDrop(&data,&source,DROPEFFECT_COPY,&mut effect);
        if result.is_err() { return Err("El destino no pudo recibir la pista".into()); }
        Ok(result == DRAGDROP_S_DROP && effect == DROPEFFECT_COPY)
    }
}

#[cfg(not(windows))]
pub fn start(_: &str) -> Result<bool, String> { Err("Arrastre nativo disponible en Windows".into()) }

#[cfg(all(test,windows))]
mod tests {
    #[test]
    fn native_shell_payload_preserves_unicode_file_path() {
        use windows::Win32::{System::{Com::{FORMATETC,DVASPECT_CONTENT},Ole::{OleInitialize,OleUninitialize,ReleaseStgMedium}},UI::Shell::{HDROP,DragQueryFileW}};
        let root=std::env::temp_dir().join(format!("rekord-ai-drag-qa-{}",std::process::id()));
        std::fs::create_dir_all(&root).unwrap();
        let path=root.join("Canción ñ 日本語.wav");std::fs::write(&path,b"fixture").unwrap();
        unsafe {
            OleInitialize(None).unwrap();
            let data=super::data_object(path.to_str().unwrap()).unwrap();
            let format=FORMATETC{cfFormat:15,dwAspect:DVASPECT_CONTENT.0,lindex:-1,tymed:1,..Default::default()};
            assert!(data.QueryGetData(&format).is_ok());
            let mut medium=data.GetData(&format).unwrap();
            let hdrop=HDROP(medium.u.hGlobal.0);
            assert_eq!(DragQueryFileW(hdrop,u32::MAX,None),1);
            let mut buffer=vec![0u16;32768];let length=DragQueryFileW(hdrop,0,Some(&mut buffer));
            let received=String::from_utf16(&buffer[..length as usize]).unwrap();
            ReleaseStgMedium(&mut medium);drop(data);OleUninitialize();
            assert_eq!(received,path.to_str().unwrap());
        }
        std::fs::remove_file(path).unwrap();std::fs::remove_dir(root).unwrap();
    }
}
